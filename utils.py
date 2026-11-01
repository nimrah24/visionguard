"""
VisionGuard - utils.py
Small helper functions shared by the other modules:
opening the video source, resizing frames, measuring FPS, drawing text
and building the DIP-stages grid.
"""

import os
import time

import cv2
import numpy as np


def open_video_source(source):
    """
    Open a webcam (if `source` is a number like "0") or a video file (if it is a path).
    Returns (capture, is_file). Returns (None, False) if it cannot be opened.
    """
    source = str(source).strip()

    if source.isdigit():
        index = int(source)
        # On Windows, the DirectShow backend (CAP_DSHOW) usually opens webcams faster.
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Fall back to OpenCV's default backend.
            cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            print(f"[ERROR] Could not open webcam {index}. "
                  "Is it in use by another app (Zoom, Teams, Camera)? "
                  "Is camera access allowed in Windows Settings > Privacy & security > Camera?")
            return None, False
        print(f"[INFO] Webcam {index} opened.")
        return cap, False

    if not os.path.isfile(source):
        print(f"[ERROR] Video file not found: {os.path.abspath(source)}")
        return None, False

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] OpenCV could not read the video file: {source} "
              "(try converting it to .mp4 with H.264 encoding).")
        return None, False
    print(f"[INFO] Video file opened: {source}")
    return cap, True


def resize_frame(frame, width):
    """Resize a frame to the given width while keeping its aspect ratio."""
    h, w = frame.shape[:2]
    if w == width:
        return frame
    new_h = int(h * width / w)
    return cv2.resize(frame, (width, new_h), interpolation=cv2.INTER_AREA)


class FPSCounter:
    """Measures frames per second, smoothed so the number does not jump around."""

    def __init__(self, smoothing=0.9):
        self.smoothing = smoothing
        self.prev_time = time.perf_counter()
        self.fps = 0.0

    def update(self):
        now = time.perf_counter()
        dt = now - self.prev_time
        self.prev_time = now
        if dt > 0:
            instant_fps = 1.0 / dt
            if self.fps == 0.0:
                self.fps = instant_fps
            else:
                self.fps = self.smoothing * self.fps + (1 - self.smoothing) * instant_fps
        return self.fps


def draw_text(frame, text, position, color=(255, 255, 255), scale=0.6, thickness=2):
    """Draw text with a dark background box so it is readable on any frame."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = position
    cv2.rectangle(frame, (x - 4, y - th - 6), (x + tw + 4, y + baseline + 2), (0, 0, 0), -1)
    cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def make_grid(images, labels, cols=2, tile_width=320):
    """
    Combine several images (colour or grayscale) into one labelled grid image.
    Used to show every DIP stage side by side in a single window.
    """
    tiles = []
    for img, label in zip(images, labels):
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        tile = resize_frame(img, tile_width).copy()  # copy so we never draw on the original
        draw_text(tile, label, (8, 22), scale=0.5, thickness=1)
        tiles.append(tile)

    # Pad with black tiles so every row is full.
    while len(tiles) % cols != 0:
        tiles.append(np.zeros_like(tiles[0]))

    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    return np.vstack(rows)
