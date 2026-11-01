"""
VisionGuard - config.py
All tunable settings live here so you never have to hunt through the code.
(Final version: capture, DIP preprocessing, detection, blind spot, tracking, risk, audio.)
"""

import os

# Folder that contains this file. Paths below are built from it, so the app finds
# its files even if you run it from a different folder (e.g. VS Code's Run button).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- Video input ----------
# 0 = default laptop webcam, 1 = second camera, or a file path like "videos/sample_road.mp4"
DEFAULT_SOURCE = 0

# True = play video files at their normal speed (good for demos).
# False = process as fast as the CPU allows (good for measuring maximum processing speed).
PLAY_VIDEO_REALTIME = True

# Every frame is resized to this width (height keeps the aspect ratio).
# Smaller frames = faster processing. 640 is a good balance for a laptop CPU.
FRAME_WIDTH = 640

# ---------- Display ----------
WINDOW_NAME = "VisionGuard"
STAGES_WINDOW_NAME = "VisionGuard - DIP Stages"
SHOW_STAGES = True          # show the 4-step DIP window at start-up (toggle with M)
STAGE_TILE_WIDTH = 320      # width of each small image in the DIP Stages window

# ---------- Preprocessing ----------
# Gaussian blur kernel size. Must be an ODD number (3, 5, 7, ...).
# Bigger = smoother image, less noise, but small details disappear.
BLUR_KERNEL_SIZE = 5

# ---------- Background subtraction (MOG2) ----------
# True  = feed MOG2 the blurred COLOUR frame. Shadow detection can then compare colour,
#         so a dark car is not mistaken for a shadow. (Recommended.)
# False = feed MOG2 the blurred GRAYSCALE frame. Faster, but in grayscale anything a bit
#         darker than the road looks like a shadow, so shadow detection is switched off
#         and real shadows will be counted as motion.
USE_COLOR_FOR_BG = True
BG_HISTORY = 500            # how many past frames shape the background model
BG_VAR_THRESHOLD = 25       # how different a pixel must be to count as "moving" (MOG2 default is 16)
DETECT_SHADOWS = True       # MOG2 marks shadows as gray (127) instead of white (255); colour mode only
BG_LEARNING_RATE = -1       # -1 = let OpenCV choose automatically; 0 = never update the background
WARMUP_FRAMES = 30          # frames needed to learn the background before results are trusted

# ---------- Thresholding ----------
# MOG2 output: 0 = background, 127 = shadow, 255 = moving object.
# Keeping only pixels above 200 removes the shadows.
MASK_THRESHOLD = 200

# ---------- Morphological operations ----------
MORPH_KERNEL_SIZE = 5       # size of the elliptical structuring element
OPEN_ITERATIONS = 1         # opening = erode then dilate -> removes small white specks
CLOSE_ITERATIONS = 2        # closing = dilate then erode -> fills small black holes in objects
DILATE_ITERATIONS = 1       # extra dilation -> joins broken pieces of the same vehicle

# If more than this fraction of the frame is "moving", the camera probably moved
# or the lighting changed suddenly. The app then suggests pressing R and skips detection.
MAX_MOTION_RATIO = 0.5

# ---------- Object detection (contours) ----------
# Blobs smaller than this many pixels are ignored as noise (leaves, insects, rain).
# Measured on the resized frame (FRAME_WIDTH wide). Raise it if you see tiny boxes.
MIN_CONTOUR_AREA = 800

# ---------- Vehicle shape filter (a heuristic, NOT true recognition) ----------
# A moving blob is labelled "LIKELY VEHICLE" only if it passes ALL of these rules.
VEHICLE_MIN_AREA = 2500     # vehicles are usually bigger than people/animals at the same distance
VEHICLE_MIN_ASPECT = 0.8    # width / height. A standing person is ~0.3-0.5 (tall and narrow)
VEHICLE_MAX_ASPECT = 4.0    # a car seen from the side is ~2-3; a truck can be ~3-4
VEHICLE_MIN_SOLIDITY = 0.6  # blob area / convex hull area. Vehicles are compact, solid shapes

# ---------- Blind-spot region ----------
# Polygon corners as FRACTIONS of the frame: (x, y) where (0, 0) = top-left and
# (1, 1) = bottom-right. Fractions keep the region in the same place at any frame size.
# Default: a trapezoid in the lower-right part of the frame (the lane next to the vehicle
# for a camera on the left mirror looking backwards). Press E in the app to draw your own.
BLINDSPOT_POLYGON = [(0.55, 0.45), (0.95, 0.45), (1.0, 1.0), (0.45, 1.0)]
BLINDSPOT_ENABLED = True        # start with the region on (toggle with B)
# An object counts as "in the blind spot" when at least this fraction of its
# bounding box lies inside the polygon (0.2 = 20 %).
BLINDSPOT_MIN_OVERLAP = 0.2
# False = warn for ANY moving object (people and bikes matter too).
# True  = warn only for objects labelled LIKELY VEHICLE.
BLINDSPOT_VEHICLES_ONLY = False

# ---------- Tracking (centroid tracker) ----------
MAX_MATCH_DISTANCE = 80     # max pixels a centroid may jump between frames and still be "the same object"
MAX_MISSED_FRAMES = 10      # delete a track after this many frames without a match
SPEED_WINDOW = 6            # number of recent positions used to measure speed (more = smoother, slower to react)

# ---------- Risk rules ----------
ZONE_CONFIRM_FRAMES = 3     # frames in a row inside the blind spot before HIGH risk (stops false flashes)
ZONE_CLEAR_FRAMES = 5       # frames in a row outside before HIGH risk ends (stops flicker)
MIN_TRACK_AGE = 3           # frames a track must exist before its speed is trusted
MIN_APPROACH_SPEED = 40     # pixels/second; slower objects (or wobbling boxes) are shown as "SLOW"
PREDICTION_SECONDS = 1.0    # MEDIUM risk if the object is predicted to be in the blind spot within this time
APPROACH_CONFIRM_FRAMES = 3 # ...and that prediction holds for this many frames in a row

# ---------- Audio alerts ----------
AUDIO_ENABLED = True                    # start with sound on (toggle with A)
WARNING_SOUND = os.path.join(BASE_DIR, "assets", "warning.wav")  # HIGH risk; created if missing
CAUTION_SOUND = os.path.join(BASE_DIR, "assets", "caution.wav")  # MEDIUM risk; created if missing
ALERT_COOLDOWN_SECONDS = 3.0            # minimum gap between two sounds of the same kind
ALERT_ON_MEDIUM = False                 # also beep softly for "approaching"? (can get annoying)

# ---------- Screenshots ----------
SCREENSHOT_DIR = os.path.join(BASE_DIR, "output", "screenshots")

# ---------- Highway simulation (python main.py with no --source) ----------
SIM_WINDOW_SIZE = (1280, 720)   # whole window; scales down automatically on small screens
SIM_VIEW_SIZE = (900, 500)      # the highway view = the "camera frame" the DIP pipeline processes
SIM_FPS = 30
SIM_PPM = 12                    # pixels per metre in the top-down view (known camera scale)
SIM_TRUCK_SCREEN_X = 400        # where the truck's centre appears; the camera rides on the truck
SIM_TRAFFIC_SIDE = "left"       # "left" = keep-left traffic (India, UK); "right" = keep-right (US, EU)
SIM_EGO_SPEED_KMH = 80          # the heavy truck's speed
SIM_DEFAULT_MODE = "DIP"        # "DIP" = OpenCV detection, "GT" = simulator ground truth

# Danger zones around the truck, in metres relative to the truck's CENTRE:
#   x = forward (+) / backward (-),  y = right (+) / left (-) of the truck.
# The truck is 16.5 m long (front at x = +8.25) and 2.55 m wide; one lane is 3.7 m.
# With keep-left traffic the driver sits on the right, so the LEFT blind spot is longer.
SIM_ZONES = {
    "LEFT":  {"label": "LEFT BLIND SPOT",   "x": (-14.0, 6.5),  "y": (-5.4, -1.4)},
    "RIGHT": {"label": "RIGHT BLIND SPOT",  "x": (-12.0, 2.0),  "y": (1.4, 5.4)},
    "FRONT": {"label": "FRONT DANGER ZONE", "x": (8.3, 16.0),   "y": (-1.6, 1.6)},
    "REAR":  {"label": "REAR DANGER ZONE",  "x": (-24.0, -8.3), "y": (-1.6, 1.6)},
}
SIM_ZONE_MIN_OVERLAP = 0.2      # fraction of a vehicle's box inside a zone to count as "in" it
SIM_CONFIRM_SECONDS = 0.1       # inside this long before a zone counts as occupied (about 3 frames)
SIM_CLEAR_SECONDS = 0.6         # outside this long before a zone warning clears

# Risk rules (relative speeds, metres per second)
SIM_PREDICT_SECONDS = 2.0       # look this far ahead for vehicles about to enter a zone
SIM_MIN_APPROACH_SPEED = 1.0    # slower relative motion is not treated as "approaching"
SIM_MEDIUM_TTE = 1.0            # predicted entry within this time -> MEDIUM
SIM_HIGH_TTE = 1.2              # predicted entry within this time AND fast -> HIGH
SIM_HIGH_APPROACH_SPEED = 6.0   # "fast" approach speed for the rule above (about 22 km/h faster)
SIM_HIGH_LATERAL_SPEED = 0.9    # sideways speed toward the truck that counts as moving into its path
                                # (a lane change here is 1.3 m/s; DIP box jitter reaches about 0.5)
SIM_HIGH_CLOSING_SPEED = 4.0    # closing speed inside the front/rear zone that is HIGH risk
SIM_HIGH_PASS_SPEED = 10.0      # passing through a side blind spot this fast is HIGH risk

# DIP detection on simulated frames (frames are 900 px wide, so areas differ from the webcam)
SIM_MIN_CONTOUR_AREA = 500      # a car is about 55 x 22 = 1200 px in the view
SIM_BG_LEARNING_RATE = 0.0002   # tiny: the truck-mounted view's road never changes, and a
                                # higher rate would absorb cars travelling at the truck's speed
SIM_ROI_MARGIN_M = 0.3          # the DIP region of interest = our carriageway's lanes + this margin
SIM_DASH_KERNEL = (3, 13)       # (width, height) of the opening that removes moving lane dashes
SIM_HIGH_CONFIRM_SECONDS = 0.25 # a HIGH condition must last this long (stops one noisy frame alarming)

# ---------- Recording (python main.py --record) ----------
RECORD_DIR = os.path.join(BASE_DIR, "output")
RECORD_WEBCAM_FPS = 20.0    # playback FPS of recorded webcam sessions (webcams rarely report a true value)
