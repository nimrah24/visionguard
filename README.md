# VisionGuard

**Digital Image Processing (DIP)-Based Collision Avoidance System for Heavy Vehicles**

VisionGuard is a college prototype that watches a camera feed, detects moving objects with
classic Digital Image Processing (no deep learning, no GPU), and warns the driver with visual
and audio alerts when an object enters a configurable blind-spot region.

> **Prototype disclaimer.** This is an educational prototype, not a safety product. It does not
> guarantee collision prevention, it does not measure real-world distance or speed, and it must
> not be relied on in a real vehicle.

---

## What it does

| Feature | Status |
|---|---|
| Webcam or video-file input (`--source`) | Implemented |
| Preprocessing: resize, optional grayscale, Gaussian blur | Implemented |
| MOG2 background subtraction with shadow removal | Implemented |
| Thresholding + morphology (opening, closing, dilation) | Implemented |
| Contours, bounding boxes, minimum-area filter | Implemented |
| "Likely vehicle" shape heuristic (area, aspect ratio, solidity) | Implemented (heuristic only) |
| Configurable polygon blind-spot region + mouse editor | Implemented |
| Centroid tracking with IDs, speed (px/s) and direction | Implemented |
| LOW / MEDIUM / HIGH risk rules with anti-flicker hysteresis | Implemented |
| Visual alerts (boxes, coloured region, warning banners) | Implemented |
| Non-blocking audio alerts with cooldown and mute | Implemented (Windows) |
| FPS display, screenshots, recording, end-of-run summary | Implemented |
| Interactive highway simulation with 7 scenarios and a safety dashboard | Implemented (main demo) |
| DIP detection mode on simulated frames + ground-truth comparison mode | Implemented |
| True vehicle recognition (e.g. YOLO) | **Not implemented**, future work |
| Real distance / time-to-collision (camera calibration) | **Not implemented**, future work |
| Working on a moving vehicle (ego-motion compensation) | **Not implemented**, future work |

---

## Project structure

```
VisionGuard/
├── main.py           Entry point: main loop, drawing, keyboard controls, summary
├── config.py         Every tunable setting in one place
├── utils.py          Open camera/video, resize, FPS counter, text drawing, image grid
├── detector.py       DIP pipeline (blur → MOG2 → threshold → morphology) + contours
├── blindspot.py      Blind-spot polygon: overlap check, drawing, mouse editor
├── tracker.py        Centroid tracker, speed/direction, risk rules
├── alerts.py         Non-blocking audio alerts with cooldown (generates default beeps)
├── simulation/       Highway demonstration (Pygame)
│   ├── world.py        road layout, vehicles, traffic movement
│   ├── scenarios.py    the 7 scripted scenarios
│   ├── renderer.py     draws the camera frame and the display overlays
│   ├── risk.py         zones, occupancy, SAFE/LOW/MEDIUM/HIGH rules (shared by both modes)
│   ├── dip_bridge.py   sends rendered frames through detector.py + tracker.py
│   ├── dashboard.py    buttons, risk panel, zone map, warnings, event log
│   └── app.py          main loop
├── requirements.txt  Python packages
├── README.md         This file
├── TEST_PLAN.md      Test cases and how to measure performance
├── assets/           warning.wav, caution.wav (created automatically on first run)
├── videos/           Put your test road videos here
└── output/           Recordings; screenshots/ holds screenshots
```

---

## Requirements

- **OS:** Windows 10/11 (audio uses the built-in `winsound` module; everything else is cross-platform)
- **Python:** 3.10 or newer (tested with 3.14)
- **Hardware:** any laptop with a webcam; no GPU needed
- **Packages:** `opencv-python`, `numpy`, `pygame-ce` (see `requirements.txt`)

---

## Setup (Windows PowerShell in VS Code)

Open the `VisionGuard` folder in VS Code (**File → Open Folder**), then open a terminal with **Ctrl + `**.

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If activation fails with *"running scripts is disabled"*:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

In VS Code, press **Ctrl+Shift+P → Python: Select Interpreter** and choose the one in `.venv`.

---

## Highway simulation (main demonstration)

```powershell
python main.py
```

With no `--source`, VisionGuard opens the **highway simulation** instead of the webcam: a top-down
multi-lane highway seen by a camera riding on a heavy truck, with cars, SUVs, vans, buses, trucks,
oncoming traffic, four translucent danger zones and a live safety dashboard.

| Control | Action |
|---|---|
| Buttons **1 to 7** (or keys 1-7) | Start a scenario; click again to replay it from the beginning |
| **Start / Pause / Resume** (Space) | Pause freezes all vehicles; resume continues |
| **Reset** (R) | Restart the current scenario paused; clears warnings, tracks and the event log |
| **0.5x / 1x / 2x** (+ / -) | Simulation speed |
| **Mode** (M) | Switch between DIP detection and Ground truth |
| **Audio** (A) / **Zones** (B) | Mute sounds / hide the zone overlays |
| Esc | Quit |

| # | Scenario | What to point out |
|---|---|---|
| 1 | Safe highway driving | STATUS SAFE; zones stay green |
| 2 | Vehicle approaching from behind | CAUTION while it closes in, then WARNING in the rear zone |
| 3 | Left-side blind-spot intrusion | WARNING: VEHICLE IN LEFT BLIND SPOT, beep |
| 4 | Right-side blind-spot intrusion | Right zone turns amber, beep |
| 5 | Multiple vehicles | Three zones occupied, separate warnings, counts |
| 6 | High-risk movement | HIGH RISK twice: a car racing through the left blind spot, then a cut-in ahead |
| 7 | Return to safe state | Warnings clear one by one after a short confirmation delay, then SAFE |

### The two modes: what is detected and what is known

| | DIP detection mode | Ground-truth mode |
|---|---|---|
| Where the boxes come from | OpenCV, from the rendered pixels only | The simulator's exact vehicle positions |
| Pipeline | ROI, blur, MOG2, threshold, opening/closing/dilation, lane-dash opening, contours, centroid tracker | none |
| Box labels | `D3 DETECTED +0.5 m/s` | `#3 CAR 101 km/h` |
| Use it to | show that image processing really finds the vehicles | demonstrate a scenario reliably, and to check DIP |

Both modes feed the **same** risk engine (`simulation/risk.py`), so any difference between them comes
from detection, not from the rules. The dashboard's *cross-check* line compares them live.

How DIP mode copes with a camera on a moving truck:
1. **The truck stays still in the frame**, because the camera rides on it, so MOG2 learns it as background.
2. **The road surface varies only across the road**, so it looks identical as it scrolls past (a simplification:
   real asphalt texture would add false motion).
3. **Region of interest:** only our carriageway's lanes are analysed; scrolling scenery and oncoming traffic are ignored.
4. **Directional opening (3 x 13 px):** removes the moving lane dashes (thin stripes) but keeps vehicles.
5. **Background initialisation** on the empty road, then a very small learning rate.
6. Pixel results are converted to metres with the known camera scale (12 px per metre).

Known DIP-mode effects you may see (and can explain): a **black car** can be removed as a "shadow"
(scenario 1), boxes are slightly larger than vehicles because of shadows and dilation, and brief
"about to enter" flickers appear while a vehicle is still sliding into view.

## Running with a camera or video

```powershell
python main.py --source 0                             # laptop webcam
python main.py --source 1                             # external USB camera
python main.py --source videos/sample_road.mp4        # video file
python main.py --source videos/sample_road.mp4 --record   # also save annotated video to output/
```

### Keyboard controls for webcam / video (click the main video window first)

| Key | Action |
|---|---|
| **Q** | Quit (closing the window also works) |
| **R** | Reset: re-learn the background and clear all tracks |
| **B** | Turn the blind-spot region on / off |
| **E** | Edit region: left-click corners, right-click to undo, **E** again to finish |
| **A** | Mute / unmute audio |
| **M** | Show / hide the DIP Stages window |
| **S** | Save a screenshot to `output/screenshots/` |

When the program ends it prints a **session summary** (frames, FPS, processing time, number
of tracked objects, frames at each risk level, alerts played). Use these numbers in your report.

### Getting test videos

Free stock sites such as Pexels or Pixabay have traffic clips (search "highway traffic", "road
side view", "traffic intersection"). Check each clip's licence. **Choose clips filmed from a fixed,
non-moving camera**; see Limitations for why.

---

## How it works (short version)

1. **Capture** a frame and resize it to 640 px wide.
2. **Blur** it (Gaussian) to suppress sensor noise.
3. **MOG2** compares each pixel to its learned background → foreground (255), shadow (127), background (0).
4. **Threshold** at 200 removes shadows → binary mask.
5. **Morphology:** opening removes specks, closing fills holes, dilation joins fragments.
6. **Contours** → bounding boxes; blobs smaller than `MIN_CONTOUR_AREA` are discarded.
7. **Shape heuristic** labels compact, wide, large blobs as "LIKELY VEHICLE".
8. **Blind-spot check:** fraction of each box inside the polygon ≥ `BLINDSPOT_MIN_OVERLAP`.
9. **Tracking:** greedy nearest-centroid matching gives IDs; speed = displacement ÷ time over the last few frames.
10. **Risk:** HIGH = confirmed inside for 3 frames; MEDIUM = entering, or predicted to enter within 1 s; LOW = otherwise.
11. **Alerts:** coloured boxes/region/banner; asynchronous beep on HIGH with a 3 s cooldown.

---

## Tuning (all in `config.py`)

| Symptom | Setting to change |
|---|---|
| Too many tiny boxes / noise | Raise `MIN_CONTOUR_AREA`, `BG_VAR_THRESHOLD` or `BLUR_KERNEL_SIZE` (odd) |
| One vehicle split into several boxes | Raise `CLOSE_ITERATIONS` / `DILATE_ITERATIONS` |
| Two vehicles merged into one box | Lower `DILATE_ITERATIONS` |
| Real vehicles not labelled LIKELY VEHICLE | Adjust `VEHICLE_MIN_AREA`, `VEHICLE_MIN_ASPECT`, `VEHICLE_MAX_ASPECT` |
| Region in the wrong place | Press **E** and redraw it, then paste the printed line into `BLINDSPOT_POLYGON` |
| Warning too slow / too jumpy | `ZONE_CONFIRM_FRAMES` (lower = faster, more false flashes) |
| Warning stays on too long | Lower `ZONE_CLEAR_FRAMES` |
| CAUTION too early / too often | Lower `PREDICTION_SECONDS`, raise `MIN_APPROACH_SPEED` |
| IDs change for fast objects | Raise `MAX_MATCH_DISTANCE` |
| Beeping too often | Raise `ALERT_COOLDOWN_SECONDS` |
| Measure maximum processing speed | Set `PLAY_VIDEO_REALTIME = False` |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'cv2'` | Activate `.venv`; select the `.venv` interpreter in VS Code; `pip install -r requirements.txt` |
| `Could not open webcam 0` | Close Zoom/Teams/Camera; Windows Settings → Privacy & security → Camera → allow desktop apps; try `--source 1` |
| Black webcam image | Privacy shutter or camera-off Fn key |
| `Video file not found` | Path is relative to the terminal's current folder; run from the `VisionGuard` folder or give the full path |
| Video won't open | Convert to .mp4 (H.264), e.g. with VLC → Convert/Save |
| Whole mask turns white / orange "LARGE CHANGE" | Camera moved or lights changed. Keep the camera still, press **R** |
| Keys do nothing | Click the **main** window (not DIP Stages) |
| No sound but `[ALERT]` lines print | Check Windows volume / output device; check `Audio: ON` on screen |
| `Audio: UNAVAILABLE` | Not on Windows, or the .wav is not PCM. Delete `assets/*.wav` to regenerate |
| Low FPS | Lower `FRAME_WIDTH` (e.g. 480); hide DIP Stages with **M**; close other apps |

---

## Limitations

- **Static camera assumption.** Background subtraction assumes the camera does not move.
  On a moving truck the whole scene moves, so the mask fills with false motion. The prototype
  is therefore suited to a **stationary vehicle** (e.g. a truck waiting at a junction, about to
  turn or pull away, with a cyclist or car in its blind spot) or a fixed test camera.
- **Lighting changes.** Sudden changes (clouds, headlights, tunnels, webcam auto-exposure)
  look like motion until the model re-adapts or **R** is pressed.
- **Shadows.** Strong shadows can survive shadow removal and enlarge boxes; dark-grey vehicles on
  grey roads can be mistaken for shadows.
- **Stationary objects disappear.** A vehicle that stops in the blind spot is gradually absorbed
  into the background and the warning will eventually end.
- **Occlusion and merging.** Overlapping objects merge into one blob; centroid tracking can swap IDs.
- **No real classification.** "LIKELY VEHICLE" is a size/shape guess; people in groups, animals or
  large shadows can pass, and some real vehicles can fail.
- **2D image only.** "In the blind spot" means "overlaps that part of the image". Speeds are in
  pixels per second, not km/h. No real distance or time-to-collision is computed.
- **Night, rain, fog, glare and camera vibration** were not handled or evaluated.

## Future enhancements

- Optional YOLO (or similar) detector to classify vehicles, cyclists and pedestrians.
- Camera calibration + ground-plane homography to estimate real distance and time-to-collision.
- Ego-motion compensation (optical flow) so the system works while the vehicle is moving.
- Kalman-filter tracking for smoother speeds and fewer ID switches.
- Multiple cameras (left, right, rear) and turn-indicator integration.
- Deployment on an embedded board (e.g. Raspberry Pi) with an in-cab display.
