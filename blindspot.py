"""
VisionGuard - blindspot.py
Phase 4: the blind-spot region.

BlindSpot     - stores the polygon, checks which detections overlap it, and draws it.
RegionEditor  - lets you draw a new polygon with the mouse (press E in the app).

The polygon is stored as fractions of the frame size (0.0 to 1.0), so it stays in
the same place whatever resolution the camera or video has.
"""

import cv2
import numpy as np

import config

RED = (0, 0, 255)
ORANGE = (0, 165, 255)
BLUE = (255, 128, 0)
WHITE = (255, 255, 255)


class BlindSpot:
    def __init__(self, points=None, enabled=None):
        self.enabled = config.BLINDSPOT_ENABLED if enabled is None else enabled
        self.set_polygon(points if points is not None else config.BLINDSPOT_POLYGON)

    def set_polygon(self, points):
        """Replace the polygon. `points` = list of (x, y) fractions."""
        if len(points) < 3:
            raise ValueError("A blind-spot polygon needs at least 3 points.")
        self.points = [(float(x), float(y)) for x, y in points]
        self._mask = None  # force the mask to be rebuilt

    def pixel_points(self, width, height):
        """Polygon corners converted from fractions to pixel coordinates."""
        return np.array([[int(x * (width - 1)), int(y * (height - 1))] for x, y in self.points],
                        dtype=np.int32)

    def _region_mask(self, height, width):
        """
        Binary image the size of the frame: 255 inside the polygon, 0 outside.
        Built once and reused until the polygon or frame size changes.
        """
        if self._mask is None or self._mask.shape != (height, width):
            self._mask = np.zeros((height, width), dtype=np.uint8)
            cv2.fillPoly(self._mask, [self.pixel_points(width, height)], 255)
        return self._mask

    def overlap(self, det, frame_shape):
        """Fraction (0.0 to 1.0) of the detection's bounding box that lies inside the polygon."""
        height, width = frame_shape[:2]
        mask = self._region_mask(height, width)
        # Clamp to the frame: a negative index would make NumPy count from the far edge.
        x0, y0 = max(det.x, 0), max(det.y, 0)
        x1, y1 = min(det.x + det.w, width), min(det.y + det.h, height)
        if x1 <= x0 or y1 <= y0:
            return 0.0
        box = mask[y0:y1, x0:x1]
        return cv2.countNonZero(box) / box.size

    def contains_point(self, point, frame_shape):
        """True if the (x, y) pixel point lies inside the polygon (False if off-screen)."""
        height, width = frame_shape[:2]
        x, y = int(round(point[0])), int(round(point[1]))
        if not (0 <= x < width and 0 <= y < height):
            return False
        return self._region_mask(height, width)[y, x] > 0

    def check(self, detections, frame_shape):
        """
        Mark every detection that is inside the blind spot (sets det.in_blindspot)
        and return the list of those detections.
        """
        inside = []
        for det in detections:
            det.in_blindspot = False
            if not self.enabled:
                continue
            if config.BLINDSPOT_VEHICLES_ONLY and not det.is_vehicle:
                continue
            if self.overlap(det, frame_shape) >= config.BLINDSPOT_MIN_OVERLAP:
                det.in_blindspot = True
                inside.append(det)
        return inside

    def draw(self, frame, level=0):
        """
        Draw the see-through region. level: 0 = clear (blue),
        1 = object approaching (orange), 2 = object inside (red).
        """
        if not self.enabled:
            return
        height, width = frame.shape[:2]
        pts = self.pixel_points(width, height)
        color = {0: BLUE, 1: ORANGE, 2: RED}[level]

        # Fill a copy, then blend it with the original -> see-through region.
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts], color)
        alpha = 0.2 if level == 0 else 0.35
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, dst=frame)
        cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)

        top = pts[np.argmin(pts[:, 1])]
        cv2.putText(frame, "BLIND SPOT", (int(top[0]) + 5, int(top[1]) + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA)


class RegionEditor:
    """
    Draw a new blind-spot polygon with the mouse.
        left click  = add a corner
        right click = remove the last corner
        press E     = finish (needs at least 3 corners)
    """

    def __init__(self):
        self.active = False
        self.points = []            # fractions, like BlindSpot.points
        self.frame_size = (1, 1)    # (width, height) of the displayed frame; set by main.py

    def start(self):
        self.active = True
        self.points = []

    def finish(self):
        """Stop editing. Returns the new points, or None if fewer than 3 were clicked."""
        self.active = False
        if len(self.points) < 3:
            return None
        return list(self.points)

    def on_mouse(self, event, x, y, flags, param):
        """Called by OpenCV for every mouse event on the main window."""
        if not self.active:
            return
        width, height = self.frame_size
        if event == cv2.EVENT_LBUTTONDOWN:
            self.points.append((round(x / (width - 1), 3), round(y / (height - 1), 3)))
        elif event == cv2.EVENT_RBUTTONDOWN and self.points:
            self.points.pop()

    def draw(self, frame):
        if not self.active:
            return
        height, width = frame.shape[:2]
        pts = [(int(x * (width - 1)), int(y * (height - 1))) for x, y in self.points]
        for p in pts:
            cv2.circle(frame, p, 5, WHITE, -1)
        if len(pts) >= 2:
            cv2.polylines(frame, [np.array(pts, dtype=np.int32)], isClosed=len(pts) >= 3,
                          color=WHITE, thickness=2)
        cv2.putText(frame, f"EDIT MODE: left click = add corner, right click = undo, "
                    f"E = finish ({len(pts)} pts)", (10, height - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, WHITE, 1, cv2.LINE_AA)
