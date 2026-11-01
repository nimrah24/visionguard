"""
VisionGuard - tracker.py
Phase 5: follow objects from frame to frame and decide how risky each one is.

CentroidTracker - gives every object an ID and matches it to the nearest
                  object in the next frame (centroid tracking).
Track           - one followed object: position history, speed, direction and
                  a "confirmed in blind spot" flag that ignores short flickers.
assess_risk     - simple, configurable rules that turn tracks into LOW / MEDIUM / HIGH risk.

Speeds are in PIXELS per second on the resized frame. They are NOT real-world
speeds: converting them would need camera calibration and the distance to the road.
"""

import math
from collections import deque

import config

RISK_LOW = 0       # moving, but not near the blind spot
RISK_MEDIUM = 1    # approaching or just entering the blind spot
RISK_HIGH = 2      # confirmed inside the blind spot
RISK_NAMES = {RISK_LOW: "LOW", RISK_MEDIUM: "MEDIUM", RISK_HIGH: "HIGH"}


class Track:
    def __init__(self, track_id, det, t):
        self.id = track_id
        self.det = det                  # latest Detection matched to this track
        # Recent (time, x, y) centroid positions, used to measure speed.
        self.history = deque([(t, *det.centroid)], maxlen=config.SPEED_WINDOW)
        self.age = 1                    # frames this track has been matched
        self.missed = 0                 # consecutive frames with no match
        self.inside_count = 0           # consecutive frames inside the blind spot
        self.outside_count = 0          # consecutive frames outside it
        self.zone_confirmed = False     # inside long enough to trust?
        self.approach_count = 0         # consecutive frames predicted to enter the blind spot
        self.risk = RISK_LOW
        self._update_zone(det.in_blindspot)

    def update(self, det, t):
        """The object was found again in this frame."""
        self.det = det
        self.history.append((t, *det.centroid))
        self.age += 1
        self.missed = 0
        self._update_zone(det.in_blindspot)

    def mark_missed(self):
        """
        The object was not found in this frame (hidden, or the mask broke up).
        Its blind-spot state is left unchanged: "not seen" is not the same as "outside",
        so a confirmed warning holds through short gaps until the track is deleted.
        """
        self.missed += 1

    def _update_zone(self, inside):
        """
        Hysteresis: the track must be inside for ZONE_CONFIRM_FRAMES frames in a row
        before the warning starts, and outside for ZONE_CLEAR_FRAMES frames in a row
        before it stops. This stops the warning flickering at the region's edge.
        """
        if inside:
            self.inside_count += 1
            self.outside_count = 0
        else:
            self.outside_count += 1
            self.inside_count = 0
        if not self.zone_confirmed and self.inside_count >= config.ZONE_CONFIRM_FRAMES:
            self.zone_confirmed = True
        elif self.zone_confirmed and self.outside_count >= config.ZONE_CLEAR_FRAMES:
            self.zone_confirmed = False

    @property
    def centroid(self):
        _, x, y = self.history[-1]
        return (x, y)

    @property
    def velocity(self):
        """(vx, vy) in pixels per second, averaged over the recent history."""
        if len(self.history) < 2:
            return (0.0, 0.0)
        t0, x0, y0 = self.history[0]
        t1, x1, y1 = self.history[-1]
        dt = t1 - t0
        if dt <= 0:
            return (0.0, 0.0)
        return ((x1 - x0) / dt, (y1 - y0) / dt)

    @property
    def speed(self):
        vx, vy = self.velocity
        return math.hypot(vx, vy)

    @property
    def direction(self):
        """Direction of movement in image terms, e.g. 'RIGHT' or 'DOWN-LEFT'."""
        if self.speed < config.MIN_APPROACH_SPEED:
            return "SLOW"  # too slow to trust the direction (could be box wobble)
        vx, vy = self.velocity
        # Angle in degrees: 0 = right, 90 = down (image y grows downwards).
        angle = math.degrees(math.atan2(vy, vx)) % 360
        names = ["RIGHT", "DOWN-RIGHT", "DOWN", "DOWN-LEFT",
                 "LEFT", "UP-LEFT", "UP", "UP-RIGHT"]
        return names[int((angle + 22.5) // 45) % 8]

    def predicted_position(self, seconds):
        """Where the centroid will be in `seconds` if it keeps the same velocity."""
        x, y = self.centroid
        vx, vy = self.velocity
        return (x + vx * seconds, y + vy * seconds)


class CentroidTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        """Forget all tracks (R key)."""
        self.tracks = {}
        self.next_id = 1

    def update(self, detections, t):
        """
        Match this frame's detections to existing tracks.
        Returns all live tracks (including ones missed for a few frames).
        """
        track_list = list(self.tracks.values())

        # Every (track, detection) pair that is close enough, nearest first.
        pairs = []
        for ti, track in enumerate(track_list):
            tx, ty = track.centroid
            for di, det in enumerate(detections):
                dx, dy = det.centroid
                dist = math.hypot(dx - tx, dy - ty)
                if dist <= config.MAX_MATCH_DISTANCE:
                    pairs.append((dist, ti, di))
        pairs.sort()

        # Greedy matching: take the closest pair, then the next closest unused pair, ...
        used_tracks, used_dets = set(), set()
        for _, ti, di in pairs:
            if ti in used_tracks or di in used_dets:
                continue
            track_list[ti].update(detections[di], t)
            used_tracks.add(ti)
            used_dets.add(di)

        # Tracks with no match: count the miss, delete them if gone too long.
        for ti, track in enumerate(track_list):
            if ti not in used_tracks:
                track.mark_missed()
                if track.missed > config.MAX_MISSED_FRAMES:
                    del self.tracks[track.id]

        # Detections with no match: a new object has appeared.
        for di, det in enumerate(detections):
            if di not in used_dets:
                self.tracks[self.next_id] = Track(self.next_id, det, t)
                self.next_id += 1

        return list(self.tracks.values())


def assess_risk(tracks, blindspot, frame_shape):
    """
    Set track.risk for every track and return the highest risk.

    HIGH   - confirmed inside the blind spot (see Track._update_zone).
    MEDIUM - inside but not confirmed yet, OR predicted to be inside the blind spot within
             PREDICTION_SECONDS for APPROACH_CONFIRM_FRAMES frames in a row.
    LOW    - everything else.
    """
    highest = RISK_LOW
    for track in tracks:
        track.risk = RISK_LOW
        if not blindspot.enabled:
            track.approach_count = 0
            continue
        if config.BLINDSPOT_VEHICLES_ONLY and not track.det.is_vehicle:
            continue

        # Is it moving towards the blind spot? (Needs a fresh match and a trusted speed.)
        approaching = (track.missed == 0
                       and track.age >= config.MIN_TRACK_AGE
                       and track.speed >= config.MIN_APPROACH_SPEED
                       and blindspot.contains_point(
                           track.predicted_position(config.PREDICTION_SECONDS), frame_shape))
        # Count consecutive frames, so a box that just wobbles does not raise a caution.
        track.approach_count = track.approach_count + 1 if approaching else 0

        if track.zone_confirmed:
            track.risk = RISK_HIGH
        elif track.missed == 0 and track.det.in_blindspot:
            track.risk = RISK_MEDIUM
        elif track.approach_count >= config.APPROACH_CONFIRM_FRAMES:
            track.risk = RISK_MEDIUM

        highest = max(highest, track.risk)
    return highest
