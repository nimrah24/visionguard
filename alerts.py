"""
VisionGuard - alerts.py
Phase 6: audio alerts.

Plays assets/warning.wav when risk becomes HIGH (and optionally assets/caution.wav
for MEDIUM). Uses `winsound`, which is built into Python on Windows, so nothing
extra has to be installed.

- Non-blocking: SND_ASYNC starts the sound and returns immediately, so the video
  keeps running while the sound plays.
- Cooldown: the same alert is not repeated more often than ALERT_COOLDOWN_SECONDS.
- If the .wav files are missing, simple beep sounds are generated automatically.
  You can replace them with your own .wav files (PCM format).
"""

import os
import time
import wave

import numpy as np

import config
from tracker import RISK_HIGH, RISK_MEDIUM

try:
    import winsound  # Windows only
except ImportError:
    winsound = None

SAMPLE_RATE = 44100


def generate_tone_wav(path, pattern, volume=0.6):
    """
    Write a simple beep sound to a .wav file.
    pattern = list of (frequency_hz, seconds); frequency 0 means silence.
    """
    parts = []
    for freq, seconds in pattern:
        t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
        if freq == 0:
            parts.append(np.zeros_like(t))
            continue
        tone = np.sin(2 * np.pi * freq * t)
        # 10 ms fade in/out so the beep does not "click".
        fade = min(len(t) // 2, int(SAMPLE_RATE * 0.01))
        envelope = np.ones_like(t)
        envelope[:fade] = np.linspace(0, 1, fade)
        envelope[-fade:] = np.linspace(1, 0, fade)
        parts.append(tone * envelope)

    samples = (np.concatenate(parts) * volume * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)          # mono
        wav.setsampwidth(2)          # 16-bit
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(samples.tobytes())


def ensure_sound_files():
    """Create the default warning/caution sounds if they don't exist yet."""
    if not os.path.isfile(config.WARNING_SOUND):
        # Urgent: three fast high/low double beeps (about 0.8 s).
        generate_tone_wav(config.WARNING_SOUND,
                          [(1000, 0.1), (750, 0.1), (0, 0.04)] * 3, volume=0.7)
        print(f"[INFO] Created default warning sound: {config.WARNING_SOUND}")
    if not os.path.isfile(config.CAUTION_SOUND):
        # Gentle: one soft beep (0.2 s).
        generate_tone_wav(config.CAUTION_SOUND, [(600, 0.2)], volume=0.4)
        print(f"[INFO] Created default caution sound: {config.CAUTION_SOUND}")


class AlertManager:
    def __init__(self):
        self.enabled = config.AUDIO_ENABLED
        self.available = winsound is not None
        self.last_played = {RISK_HIGH: float("-inf"), RISK_MEDIUM: float("-inf")}
        self.sounds = {RISK_HIGH: config.WARNING_SOUND, RISK_MEDIUM: config.CAUTION_SOUND}

        if not self.available:
            print("[WARN] winsound not available (not Windows). Audio alerts disabled; "
                  "visual alerts still work.")
            return
        try:
            ensure_sound_files()
        except OSError as err:
            print(f"[WARN] Could not create sound files ({err}). Audio alerts disabled.")
            self.available = False

    def update(self, risk, now=None, medium=None):
        """
        Call once per frame with the current highest risk.
        Plays a sound only if it is allowed by the cooldown. Returns True if a sound started.
        medium overrides config.ALERT_ON_MEDIUM (the simulation always beeps on zone entry).
        """
        if not (self.enabled and self.available):
            return False
        allow_medium = config.ALERT_ON_MEDIUM if medium is None else medium
        if risk == RISK_MEDIUM and not allow_medium:
            return False
        if risk not in self.sounds:
            return False  # LOW risk: nothing to play

        now = time.perf_counter() if now is None else now
        if now - self.last_played[risk] < config.ALERT_COOLDOWN_SECONDS:
            return False  # still cooling down

        self.last_played[risk] = now
        return self._play(self.sounds[risk])

    def _play(self, path):
        try:
            # SND_ASYNC = start playing and return immediately (no freezing).
            # A new sound replaces one that is still playing, so HIGH can interrupt MEDIUM.
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        except RuntimeError as err:
            print(f"[WARN] Could not play {path} ({err}). Audio alerts disabled.")
            self.available = False
            return False

    def toggle(self):
        """Mute / unmute (A key). Muting also stops a sound that is playing."""
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop()
        return self.enabled

    def stop(self):
        if self.available:
            winsound.PlaySound(None, 0)

    @property
    def status(self):
        if not self.available:
            return "UNAVAILABLE"
        return "ON" if self.enabled else "MUTED"
