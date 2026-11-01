"""
VisionGuard - main.py
Complete prototype: capture + DIP preprocessing + detection + blind spot + tracking + audio alerts.

Run:
    python main.py                               (highway simulation, the main demonstration)
    python main.py --source 0                    (laptop webcam)
    python main.py --source 1                    (second camera)
    python main.py --source videos/sample_road.mp4
    python main.py --source videos/sample_road.mp4 --record   (also save the annotated video)

The simulation has its own keys and buttons (see simulation/app.py).
Keys for webcam / video mode (click the video window first):
    Q = quit
    R = reset (re-learn the background and forget all tracks)
    B = turn the blind-spot region on / off
    E = draw a new blind-spot region with the mouse (press E again to finish)
    A = mute / unmute audio alerts
    M = show / hide the DIP Stages window
    S = save a screenshot to output/screenshots
"""

import argparse
import os
import sys
import time

import cv2

import config
from alerts import AlertManager
from blindspot import BlindSpot, RegionEditor
from detector import MotionDetector
from tracker import RISK_HIGH, RISK_MEDIUM, RISK_NAMES, CentroidTracker, assess_risk
from utils import FPSCounter, draw_text, make_grid, open_video_source, resize_frame

# OpenCV colours are (Blue, Green, Red).
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
ORANGE = (0, 165, 255)
CYAN = (255, 255, 0)
RED = (0, 0, 255)
WHITE = (255, 255, 255)


def parse_args():
    parser = argparse.ArgumentParser(description="VisionGuard - DIP-based blind-spot warning")
    parser.add_argument(
        "--source",
        default=None,
        help="Webcam index (0, 1, ...) or path to a video file. "
             "Leave it out to start the highway simulation.",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Save the annotated video to the output folder",
    )
    return parser.parse_args()


def get_status(detector, motion_ratio, visible_tracks, risk):
    """Choose the status message and its colour for the current frame."""
    if not detector.is_ready:
        return f"LEARNING BACKGROUND ({detector.frame_count}/{config.WARMUP_FRAMES})", YELLOW
    if motion_ratio > config.MAX_MOTION_RATIO:
        return "LARGE CHANGE - camera moved or lighting changed? Press R", ORANGE
    if risk == RISK_HIGH:
        return "WARNING: OBJECT IN BLIND SPOT", RED
    if risk == RISK_MEDIUM:
        return "CAUTION: OBJECT APPROACHING BLIND SPOT", ORANGE
    if visible_tracks:
        return f"MOVING OBJECT DETECTED ({len(visible_tracks)})", GREEN
    return "NO MOVING OBJECTS", GREEN


def draw_tracks(frame, tracks):
    """Draw box, ID, label, speed and a direction arrow for every visible track."""
    for track in tracks:
        det = track.det
        if track.risk == RISK_HIGH:
            color, label = RED, "IN BLIND SPOT"
        elif track.risk == RISK_MEDIUM:
            color, label = ORANGE, "APPROACHING"
        elif det.is_vehicle:
            color, label = CYAN, "LIKELY VEHICLE"
        else:
            color, label = GREEN, "MOVING OBJECT"

        thickness = 3 if track.risk == RISK_HIGH else 2
        cv2.rectangle(frame, (det.x, det.y), (det.x + det.w, det.y + det.h), color, thickness)

        # Arrow = where the object will be in 0.5 s at its current velocity.
        cx, cy = track.centroid
        cv2.circle(frame, (cx, cy), 4, color, -1)
        if track.speed >= config.MIN_APPROACH_SPEED:
            px, py = track.predicted_position(0.5)
            cv2.arrowedLine(frame, (cx, cy), (int(px), int(py)), color, 2, tipLength=0.3)

        line1 = f"ID {track.id} {label}"
        line2 = f"{track.speed:.0f} px/s {track.direction}"
        top = det.y - 30 if det.y > 50 else det.y + det.h + 20
        draw_text(frame, line1, (det.x, top), color=color, scale=0.45, thickness=1)
        draw_text(frame, line2, (det.x, top + 20), color=color, scale=0.45, thickness=1)


def draw_warning_banner(frame, risk, top=130, height=40):
    """
    See-through coloured bar under the info lines: red for HIGH risk, orange for MEDIUM.
    It sits near the top so it never covers the blind-spot lane (usually the lower part).
    """
    if risk == RISK_HIGH:
        color, text = RED, "WARNING: OBJECT IN BLIND SPOT"
    elif risk == RISK_MEDIUM:
        color, text = ORANGE, "CAUTION: OBJECT APPROACHING"
    else:
        return
    w = frame.shape[1]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, top), (w, top + height), color, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, dst=frame)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    cv2.putText(frame, text, ((w - tw) // 2, top + (height + th) // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, WHITE, 2, cv2.LINE_AA)


def save_screenshot(frame):
    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(config.SCREENSHOT_DIR, time.strftime("visionguard_%Y%m%d_%H%M%S.png"))
    cv2.imwrite(path, frame)
    print(f"[INFO] Screenshot saved: {path}")


def create_recorder(frame, fps):
    """Open an .mp4 file for writing annotated frames. Returns (writer, path) or (None, None)."""
    os.makedirs(config.RECORD_DIR, exist_ok=True)
    path = os.path.join(config.RECORD_DIR, time.strftime("visionguard_%Y%m%d_%H%M%S.mp4"))
    h, w = frame.shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        print("[WARN] Could not start recording. Continuing without it.")
        return None, None
    print(f"[INFO] Recording to: {path}")
    return writer, path


def print_summary(stats, runtime, tracker, alerts_played):
    """Numbers measured during this run, for your test report."""
    frames = stats["frames"]
    if frames == 0:
        print("[INFO] No frames were processed.")
        return
    avg_proc_ms = max(stats["proc_time"] / frames * 1000, 0.001)
    print("\n========== VisionGuard session summary ==========")
    print(f"Frames processed        : {frames}")
    print(f"Run time                : {runtime:.1f} s")
    print(f"Average displayed FPS   : {frames / runtime:.1f}")
    print(f"Average processing time : {avg_proc_ms:.1f} ms/frame "
          f"(max possible ~{1000 / avg_proc_ms:.0f} FPS)")
    print(f"Objects tracked (IDs)   : {tracker.next_id - 1}")
    print(f"Frames with MEDIUM risk : {stats['medium_frames']}")
    print(f"Frames with HIGH risk   : {stats['high_frames']}")
    print(f"Audio alerts played     : {alerts_played}")
    print("=================================================")


def main():
    args = parse_args()

    if args.source is None:
        # No camera or video given: run the highway simulation (no webcam is opened).
        from simulation.app import run as run_simulation
        run_simulation()
        return

    cap, is_file = open_video_source(args.source)
    if cap is None:
        sys.exit(1)

    source_label = "VIDEO FILE" if is_file else f"WEBCAM {args.source}"
    # For video files, time comes from the frame number, so speeds stay correct even
    # if your laptop processes the video slower or faster than real time.
    video_fps = cap.get(cv2.CAP_PROP_FPS) if is_file else 0
    if is_file and not video_fps > 0:
        video_fps = 30.0
    frame_index = 0
    start_time = time.perf_counter()

    fps_counter = FPSCounter()
    detector = MotionDetector()
    tracker = CentroidTracker()
    blindspot = BlindSpot()
    editor = RegionEditor()
    alerts = AlertManager()
    show_stages = config.SHOW_STAGES
    recorder = None
    stats = {"frames": 0, "proc_time": 0.0, "medium_frames": 0, "high_frames": 0}
    alerts_played = 0

    cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(config.WINDOW_NAME, editor.on_mouse)
    print("[INFO] Keys: Q = quit, R = reset, B = blind spot on/off, E = edit region, "
          "A = mute, M = DIP stages, S = screenshot.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                if is_file:
                    print("[INFO] End of video reached.")
                else:
                    print("[ERROR] Lost connection to the webcam.")
                break

            proc_start = time.perf_counter()
            frame = resize_frame(frame, config.FRAME_WIDTH)
            editor.frame_size = (frame.shape[1], frame.shape[0])
            t = frame_index / video_fps if is_file else time.perf_counter() - start_time
            frame_index += 1

            # ---- Phase 2: DIP pipeline ----
            mask = detector.get_motion_mask(frame)
            ratio = detector.motion_ratio(mask)

            # ---- Phase 3: moving-object detection ----
            # Skip while the background is still being learned, or when the whole
            # frame changed (camera moved / lights switched), because the boxes would be nonsense.
            if detector.is_ready and ratio <= config.MAX_MOTION_RATIO:
                detections = detector.find_objects(mask)
            else:
                detections = []

            # ---- Phase 4: blind-spot check (per detection) ----
            blindspot.check(detections, frame.shape)

            # ---- Phase 5: tracking + risk ----
            tracks = tracker.update(detections, t)
            risk = assess_risk(tracks, blindspot, frame.shape)
            visible = [tr for tr in tracks if tr.missed == 0]

            # ---- Phase 6: audio alert (non-blocking, with cooldown) ----
            if alerts.update(risk):
                alerts_played += 1
                print(f"[ALERT] {RISK_NAMES[risk]} risk sound played.")

            # Draw: region first (underneath), then boxes, then text on top.
            blindspot.draw(frame, level=risk)
            draw_tracks(frame, visible)
            editor.draw(frame)
            if not editor.active:
                draw_warning_banner(frame, risk)

            fps = fps_counter.update()
            status, status_color = get_status(detector, ratio, visible, risk)
            vehicles = sum(1 for tr in visible if tr.det.is_vehicle)

            draw_text(frame, f"FPS: {fps:.1f}   Audio: {alerts.status}", (10, 25))
            draw_text(frame, f"Source: {source_label}", (10, 55))
            draw_text(frame, f"Tracked: {len(visible)}  Likely vehicles: {vehicles}  "
                             f"Blind spot: {'ON' if blindspot.enabled else 'OFF'}", (10, 85))
            draw_text(frame, f"Risk: {RISK_NAMES[risk]} | {status}", (10, 115), color=status_color)

            # Statistics for the end-of-run summary.
            stats["frames"] += 1
            stats["proc_time"] += time.perf_counter() - proc_start
            stats["medium_frames"] += risk == RISK_MEDIUM
            stats["high_frames"] += risk == RISK_HIGH

            if args.record:
                if recorder is None:
                    recorder, _ = create_recorder(frame, video_fps if is_file
                                                  else config.RECORD_WEBCAM_FPS)
                    if recorder is None:
                        args.record = False
                if recorder is not None:
                    recorder.write(frame)

            cv2.imshow(config.WINDOW_NAME, frame)
            if show_stages:
                grid = make_grid(list(detector.stages.values()), list(detector.stages.keys()),
                                 cols=2, tile_width=config.STAGE_TILE_WIDTH)
                cv2.imshow(config.STAGES_WINDOW_NAME, grid)

            # waitKey(ms) waits for a key press AND lets OpenCV refresh the windows.
            # For video files, wait until this frame's real time so playback is not sped up.
            delay_ms = 1
            if is_file and config.PLAY_VIDEO_REALTIME:
                ahead = start_time + frame_index / video_fps - time.perf_counter()
                delay_ms = max(1, int(ahead * 1000))
            key = cv2.waitKey(delay_ms) & 0xFF
            if key in (ord("q"), ord("Q")):
                print("[INFO] Quit requested.")
                break
            if key in (ord("r"), ord("R")):
                detector.reset()
                tracker.reset()
                print("[INFO] Background and tracks reset. Keep the camera still while it re-learns.")
            if key in (ord("b"), ord("B")):
                blindspot.enabled = not blindspot.enabled
                print(f"[INFO] Blind-spot region {'enabled' if blindspot.enabled else 'disabled'}.")
            if key in (ord("e"), ord("E")):
                if not editor.active:
                    editor.start()
                    print("[INFO] Edit mode: click the corners of the new region, then press E.")
                else:
                    points = editor.finish()
                    if points is None:
                        print("[INFO] Edit cancelled (need at least 3 corners). Region unchanged.")
                    else:
                        blindspot.set_polygon(points)
                        print("[INFO] New region set. To keep it, paste this line into config.py:")
                        print(f"BLINDSPOT_POLYGON = {points}")
            if key in (ord("a"), ord("A")):
                print(f"[INFO] Audio alerts {'on' if alerts.toggle() else 'muted'}.")
            if key in (ord("m"), ord("M")):
                show_stages = not show_stages
                if not show_stages:
                    cv2.destroyWindow(config.STAGES_WINDOW_NAME)
                print(f"[INFO] DIP Stages window {'shown' if show_stages else 'hidden'}.")
            if key in (ord("s"), ord("S")):
                save_screenshot(frame)

            # Stop if the user closed the main window with the X button.
            if cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                print("[INFO] Window closed.")
                break
    finally:
        # Always runs, even after an error: frees the camera so other apps can use it.
        alerts.stop()
        if recorder is not None:
            recorder.release()
            print("[INFO] Recording saved.")
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Camera released.")
        print_summary(stats, time.perf_counter() - start_time, tracker, alerts_played)


if __name__ == "__main__":
    main()
