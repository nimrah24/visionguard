# VisionGuard Test Plan

Fill in the **Result** and **Notes** columns with what you actually observe. Do not copy
expected values into the result column. If a test fails, write that down: an honest
failed test with an explanation is worth more in a review than a table of invented passes.

**Test environment** (fill in):

| Item | Value |
|---|---|
| Laptop / CPU | |
| RAM | |
| Webcam resolution | |
| OS / Python version | |
| OpenCV version (`python -c "import cv2; print(cv2.__version__)"`) | |
| Test videos used (name, length, resolution, source) | |
| `FRAME_WIDTH` and other non-default settings | |

---

## 1. Functional test cases

| ID | Test | Steps | Expected result | Result (Pass/Fail) | Notes |
|---|---|---|---|---|---|
| T01 | Webcam opens | `python main.py` | Live video, FPS shown, "LEARNING BACKGROUND" then "NO MOVING OBJECTS" | | |
| T02 | Video file opens | `python main.py --source videos/<clip>.mp4` | Video plays at normal speed, ends with "End of video reached" | | |
| T03 | Invalid video path | `--source videos/does_not_exist.mp4` | Clear error message, program exits, no crash | | |
| T04 | Invalid camera index | `--source 7` | "Could not open webcam 7" message, no crash | | |
| T05 | Moving object detected | Walk across the webcam view | Box follows the person, status "MOVING OBJECT DETECTED" | | |
| T06 | Moving vehicles detected | Road clip | Most passing vehicles get a box | | Count in §3 |
| T07 | Stationary background filtered | Empty, still scene for 30 s | No boxes on walls, furniture, parked cars | | |
| T08 | Small objects filtered | Move a small object (pen) far from the camera | No box; increasing `MIN_CONTOUR_AREA` removes remaining small boxes | | Value used: |
| T09 | Shadow handling | Move near a lamp; watch DIP Stages tiles 2 and 3 | Shadow grey in tile 2, removed in tile 3 | | |
| T10 | Vehicle vs. person label | Person standing / road clip with cars | Person: "MOVING OBJECT"; most cars: "LIKELY VEHICLE" | | |
| T11 | Blind-spot region drawn | Start app | Blue see-through polygon labelled "BLIND SPOT" | | |
| T12 | Visual warning on entry | Walk into region | Region, box and banner turn red: "WARNING: OBJECT IN BLIND SPOT" | | |
| T13 | Warning clears on exit | Leave region | Returns to blue/green within ~5 frames | | |
| T14 | Approach caution | Walk towards region | Orange "CAUTION" before entering | | |
| T15 | Region toggle | Press **B** | Region hidden; no warnings even inside it | | |
| T16 | Region editor | Press **E**, click 4 corners, press **E** | New region used; config line printed | | |
| T17 | Tracking across frames | Walk slowly across the view | Same ID for the whole crossing | | |
| T18 | Direction and speed | Walk left, then right; slow, then fast | Direction label flips; px/s rises when faster | | |
| T19 | Audio alert plays | Enter region | Beep at the same time as the red warning | | |
| T20 | Audio does not freeze video | Watch FPS while it beeps | No visible stutter; FPS roughly unchanged | | FPS before/during: |
| T21 | Alerts do not repeat continuously | Stay in region 10 s | About 4 beeps (cooldown 3 s), not continuous | | `[ALERT]` lines counted: |
| T22 | Mute | Press **A**, enter region | Red warning, no sound, "Audio: MUTED" | | |
| T23 | Reset | Press **R** | "LEARNING BACKGROUND" again; IDs restart at 1 | | |
| T24 | Lighting change | Switch a room light | Orange "LARGE CHANGE"; recovers after **R** or a few seconds | | |
| T25 | No objects | Empty scene | "NO MOVING OBJECTS", no errors | | |
| T26 | Clean exit (Q) | Press **Q** | Window closes, webcam light off, summary printed | | |
| T27 | Clean exit (window X) | Click the window's X | Same as T26 | | |
| T28 | Screenshot / recording | Press **S**; run with `--record` | PNG in `output/screenshots/`; MP4 in `output/` that plays | | |

---

## 2. Measuring FPS

1. Set `PLAY_VIDEO_REALTIME = False` in `config.py` (so video files are not slowed to normal speed).
2. Run each source for at least 60 seconds and quit with **Q**.
3. Read the **session summary**: *Average displayed FPS* and *Average processing time (ms/frame)*.
4. Repeat 3 times and report the average. Also try with DIP Stages hidden (**M**) and with
   `FRAME_WIDTH = 480` / `960` to show the speed-vs-resolution trade-off.
5. Set `PLAY_VIDEO_REALTIME` back to `True` afterwards.

| Source | FRAME_WIDTH | DIP Stages | Run 1 FPS | Run 2 FPS | Run 3 FPS | Avg ms/frame |
|---|---|---|---|---|---|---|
| Webcam | 640 | shown | | | | |
| Webcam | 640 | hidden | | | | |
| Road video | 640 | hidden | | | | |
| Road video | 480 | hidden | | | | |

Note: webcams are usually capped at 30 FPS, so the *processing time* is the better measure of
how fast the algorithm itself is.

---

## 3. Measuring detection performance

Use a road clip and **manual counting** (this is called creating "ground truth").

1. Run with `--record` so you can replay the annotated video.
2. Pick at least 20 frames spread across the clip (e.g. every 2 seconds). Pause the recording
   in a video player (VLC: **E** steps one frame) or press **S** live to save them.
3. For each frame count:
   - **TP** (true positive): a real vehicle with a box on it.
   - **FP** (false positive): a box on something that is not a vehicle (shadow, tree, person if you only count vehicles).
   - **FN** (false negative / missed detection): a real moving vehicle with no box.
4. Compute:

```
Precision = TP / (TP + FP)       → "of the boxes, how many were right?"
Recall    = TP / (TP + FN)       → "of the vehicles, how many were found?"
False positives per frame = total FP / number of frames
```

| Frame | Vehicles present | TP | FP | FN | Notes (shadow, occlusion, far away ...) |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| ... | | | | | |
| **Total** | | | | | |

Do this separately for the **"LIKELY VEHICLE" label** (was the label correct?) and for
**detection only** (did the vehicle get any box?). The gap between the two shows how much the
shape heuristic helps or hurts.

### Blind-spot alert evaluation

Watch the whole clip and, for every vehicle that really passes through the blind-spot region, note:

| Event | Vehicle really in region? | HIGH warning shown? | Delay (frames) | Audio played? |
|---|---|---|---|---|
| 1 | | | | |

- **Missed alert:** vehicle in region, no HIGH warning.
- **False alert:** HIGH warning with no real object in region.
- **Delay:** frames between the vehicle entering and the warning (expected ≥ `ZONE_CONFIRM_FRAMES`).

### Tracking evaluation

For 10 vehicles, count **ID switches** (the ID number changes while it is the same vehicle).
Report the total and the average per vehicle.

---

## 4. Known failure cases to test and document

Run these on purpose and record what happens; they make good discussion points:

| Case | How to reproduce | What to observe |
|---|---|---|
| Camera movement | Gently move the laptop | Mask fills with white, "LARGE CHANGE" |
| Sudden lighting | Light switch / open curtains | False detections until re-learned |
| Webcam auto-exposure | Walk close to the camera | Background brightness shifts |
| Strong shadows | Sunlit road clip | Boxes include the shadow |
| Occlusion | Two people/cars crossing | Merged box, possible ID swap |
| Object stops in region | Stand still in the region for ~30 s | Gradually absorbed into background, warning ends |
| Misclassification | Two people side by side / large dog | May be labelled "LIKELY VEHICLE" |
| Moving-camera footage | A dashcam clip from a moving vehicle | Whole scene detected as motion (static-camera assumption) |
