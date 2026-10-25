#!/usr/bin/env python3
"""
v5_counter.py - run the v5 density model on the Pi and turn raw counts into a stable number.

  from v5_counter import V5Counter, ZoneSmoother
  counter  = V5Counter("classcan_v5_final.tflite")          # flip_avg=True costs 2x time, test it first
  smoother = ZoneSmoother(n_zones=4, window=3, max_per_zone=15)

  # for each servo position (quadrant q) after the ESP32 reports 'idle':
  raw = counter.count(frame_bgr)             # float, already calibrated
  smoother.add(q, raw)
  ...
  shown = smoother.display()                 # int to send to the LCD / dashboard

Preprocessing is IDENTICAL to training (PIL bilinear, gray-114 letterbox, 0-255 floats, RGB).
Do not replace it with cv2.resize: it shifts counts.

Calibration: pass calib=(a, b) so count = a*raw + b. Take a and b from the harness
('LOSO linear calibration'); leave (1.0, 0.0) until the harness says it is worth it.

CLI test:  python v5_counter.py model.tflite frame.jpg [--flip]
"""
import sys
from collections import deque

import numpy as np
from PIL import Image


def load_interpreter(path):
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter
    it = Interpreter(model_path=path)
    it.allocate_tensors()
    return it


def preprocess(frame_bgr, size, mode="letterbox", pad=114):
    """BGR uint8 frame -> float32 (1, size, size, 3), 0-255, RGB, exactly like training."""
    img = Image.fromarray(np.ascontiguousarray(frame_bgr[:, :, ::-1]))
    w, h = img.size
    if mode == "stretch":
        arr = np.asarray(img.resize((size, size), Image.BILINEAR), dtype=np.float32)
    else:
        s = min(size / w, size / h)
        nw, nh = int(round(w * s)), int(round(h * s))
        canvas = Image.new("RGB", (size, size), (pad, pad, pad))
        canvas.paste(img.resize((nw, nh), Image.BILINEAR), ((size - nw) // 2, (size - nh) // 2))
        arr = np.asarray(canvas, dtype=np.float32)
    return arr[None]


class V5Counter:
    def __init__(self, model_path=None, mode="letterbox", pad=114, flip_avg=False,
                 calib=(1.0, 0.0), interpreter=None):
        self.it = interpreter or load_interpreter(model_path)
        self.inp = self.it.get_input_details()[0]
        self.out = self.it.get_output_details()[0]
        self.size = int(self.inp["shape"][1])
        self.mode, self.pad, self.flip_avg, self.calib = mode, pad, flip_avg, calib

    def _raw(self, frame_bgr):
        self.it.set_tensor(self.inp["index"], preprocess(frame_bgr, self.size, self.mode, self.pad))
        self.it.invoke()
        return float(self.it.get_tensor(self.out["index"]).sum())

    def count(self, frame_bgr):
        raw = self._raw(frame_bgr)
        if self.flip_avg:
            raw = 0.5 * (raw + self._raw(frame_bgr[:, ::-1]))
        a, b = self.calib
        return max(0.0, a * raw + b)


class ZoneSmoother:
    """Median of the last `window` captures per zone, summed over zones, with display
    hysteresis so the LCD does not flicker between neighbouring integers."""

    def __init__(self, n_zones=4, window=3, max_per_zone=None, hysteresis=1.2):
        self.buf = [deque(maxlen=window) for _ in range(n_zones)]
        self.max_per_zone, self.hyst, self.shown = max_per_zone, hysteresis, None

    def add(self, zone, value):
        if self.max_per_zone is not None:
            value = min(value, self.max_per_zone)
        self.buf[zone].append(float(value))

    def zone_count(self, zone):
        return float(np.median(self.buf[zone])) if self.buf[zone] else 0.0

    def total(self):
        return sum(self.zone_count(z) for z in range(len(self.buf)))

    def display(self):
        t = self.total()
        if self.shown is None or abs(t - self.shown) > self.hyst:
            self.shown = int(round(t))
        return self.shown


if __name__ == "__main__":
    import cv2
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    c = V5Counter(sys.argv[1], flip_avg="--flip" in sys.argv)
    img = cv2.imread(sys.argv[2])
    print(f"count: {c.count(img):.2f}  (input {c.size}px, mode {c.mode}, flip_avg {c.flip_avg})")