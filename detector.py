"""
VisionGuard - detector.py
The Digital Image Processing pipeline.

Phase 2: turns a colour frame into a clean black-and-white "motion mask"
         (white = moving pixels, black = background).
Phase 3: finds the separate white blobs (contours), puts a bounding box around
         each, removes small ones, and labels vehicle-shaped ones "LIKELY VEHICLE".

Pipeline:
    colour frame -> (grayscale, optional) -> Gaussian blur -> MOG2 background subtraction
                 -> threshold (remove shadows) -> opening -> closing -> dilation
                 -> contours -> area filter -> shape filter -> detections
"""

from dataclasses import dataclass

import cv2

import config


@dataclass
class Detection:
    """One moving object found in a frame."""
    x: int              # top-left corner of the bounding box
    y: int
    w: int              # box width and height in pixels
    h: int
    area: float         # number of pixels inside the contour
    aspect: float       # w / h
    solidity: float     # contour area / convex hull area (1.0 = perfectly solid)
    is_vehicle: bool    # passed the vehicle shape rules?
    in_blindspot: bool = False  # set by blindspot.py (Phase 4)

    @property
    def centroid(self):
        """Centre point of the bounding box."""
        return (self.x + self.w // 2, self.y + self.h // 2)


def looks_like_vehicle(area, aspect, solidity):
    """
    Simple shape rules. This is a guess based on size and shape, NOT real recognition:
    a large dog, a group of people or a big shadow can still pass.
    """
    return (area >= config.VEHICLE_MIN_AREA
            and config.VEHICLE_MIN_ASPECT <= aspect <= config.VEHICLE_MAX_ASPECT
            and solidity >= config.VEHICLE_MIN_SOLIDITY)


class MotionDetector:
    def __init__(self, learning_rate=None):
        # Structuring element: the small "brush" shape used by morphological operations.
        size = config.MORPH_KERNEL_SIZE
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        # Optional fixed MOG2 learning rate used AFTER warm-up (the highway simulation
        # uses a very small one). None = always use config.BG_LEARNING_RATE.
        self.learning_rate = learning_rate
        self.reset()

    def reset(self):
        """Forget the learned background. Called at start-up and when R is pressed."""
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=config.BG_HISTORY,
            varThreshold=config.BG_VAR_THRESHOLD,
            # Grayscale has no colour to tell a shadow from a dark car, so shadows are off there.
            detectShadows=config.DETECT_SHADOWS and config.USE_COLOR_FOR_BG,
        )
        self.frame_count = 0
        # Intermediate images, kept so main.py can display every DIP step.
        self.stages = {}

    @property
    def is_ready(self):
        """True once enough frames have been seen to trust the background model."""
        return self.frame_count >= config.WARMUP_FRAMES

    def preprocess(self, frame):
        """
        (Optional) grayscale + Gaussian blur. Returns the image that is fed to MOG2.
        """
        if not config.USE_COLOR_FOR_BG:
            # One brightness channel instead of three colour channels: 3x less data.
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Each pixel becomes a weighted average of its neighbours, which removes
        # camera sensor noise that would otherwise look like tiny "motion".
        k = config.BLUR_KERNEL_SIZE
        return cv2.GaussianBlur(frame, (k, k), 0)

    def get_motion_mask(self, frame):
        """Run the full DIP pipeline on one frame and return the cleaned binary mask."""
        blurred = self.preprocess(frame)

        # MOG2 models every pixel's normal brightness as a mix of Gaussians.
        # Pixels that don't fit the model are foreground (255) or shadow (127).
        rate = config.BG_LEARNING_RATE
        if self.learning_rate is not None and self.is_ready:
            rate = self.learning_rate
        raw_mask = self.bg_subtractor.apply(blurred, learningRate=rate)
        self.frame_count += 1

        # Keep only strong foreground pixels; shadows (127) and background (0) become 0.
        _, thresh = cv2.threshold(raw_mask, config.MASK_THRESHOLD, 255, cv2.THRESH_BINARY)

        # Opening (erode -> dilate): deletes white specks smaller than the kernel.
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, self.kernel,
                                  iterations=config.OPEN_ITERATIONS)
        # Closing (dilate -> erode): fills small black holes inside objects.
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, self.kernel,
                                  iterations=config.CLOSE_ITERATIONS)
        # Dilation: grows white regions so separate pieces of one vehicle join up.
        clean = cv2.dilate(closed, self.kernel, iterations=config.DILATE_ITERATIONS)

        self.stages = {
            "1. Blurred colour" if config.USE_COLOR_FOR_BG else "1. Blurred grayscale": blurred,
            "2. MOG2 raw (gray = shadow)": raw_mask,
            "3. Threshold (shadows removed)": thresh,
            "4. Open + Close + Dilate": clean,
        }
        return clean

    @staticmethod
    def motion_ratio(mask):
        """Fraction of the frame (0.0 to 1.0) that is marked as moving."""
        return cv2.countNonZero(mask) / mask.size

    @staticmethod
    def find_objects(mask, min_area=None):
        """
        Phase 3: turn the white blobs in the mask into a list of Detection objects.
        min_area overrides config.MIN_CONTOUR_AREA (the simulation uses its own value).
        """
        if min_area is None:
            min_area = config.MIN_CONTOUR_AREA
        # RETR_EXTERNAL = only outer outlines (ignore holes inside a blob).
        # CHAIN_APPROX_SIMPLE = store only the corner points of each outline to save memory.
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue  # too small: noise

            x, y, w, h = cv2.boundingRect(contour)
            aspect = w / h
            # Convex hull = the outline you would get by stretching a rubber band around the blob.
            hull_area = cv2.contourArea(cv2.convexHull(contour))
            solidity = area / hull_area if hull_area > 0 else 0.0

            detections.append(Detection(
                x, y, w, h, area, aspect, solidity,
                is_vehicle=looks_like_vehicle(area, aspect, solidity),
            ))

        # Biggest objects first: they are usually the closest and most important.
        detections.sort(key=lambda d: d.area, reverse=True)
        return detections
