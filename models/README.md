# models/

Place trained and exported `.tflite` model files here.

## Model Files

---

### PRIMARY: `classcan_density_float32.tflite` ← **DEPLOY THIS**

> **This file must be regenerated** from the adopted checkpoint `classcan_density_v4_hardneg_ft_epoch4.weights.h5`.
> The OLD float32 file (from `classcan_density_v4_best`) is no longer the correct shipped model.

Density-map regression model: MobileNetV3-Large backbone + progressive upsampling decoder → 104×104 spatial density map (Softplus activation, 3.6M parameters).

Export command:
```bash
python scripts/export_to_tflite.py \
    --mode    density \
    --weights path/to/classcan_density_v4_hardneg_ft_epoch4.weights.h5 \
    --output  models/classcan_density_float32.tflite \
    --quant   float32
```

**Checkpoint location (Colab Drive):** `/content/drive/MyDrive/models/classcan_density_v4_hardneg_ft_epoch4.weights.h5`

**Provenance:**
- Base model: `classcan_density_v4_best.weights.h5` (SCUT-HEAD+local, MAE=2.13, r=0.9951 on 407 images)
- Fine-tuned: 8 epochs, LR=1e-5, 85%/15% SCUT-HEAD/hard-negative mix (176 manually confirmed false-positive crops)
- Best epoch: **epoch 4** (SCUT-HEAD MAE=2.35, r=0.9908; real-footage MAE=3.87 ↓59%, r=0.448 ↑ from 0.373)
- With post-inference threshold=0.15: real-footage MAE=3.08, bias=-0.73 (near-zero)

**SCUT-HEAD eval (407 images) — baseline held:**
- MAE = 2.35 people, r = 0.9908

**Real-footage eval (5 clips, 117 frames) — before vs after:**
| | Pre-fine-tune | Post-fine-tune (raw) | Post + threshold=0.15 |
|---|:---:|:---:|:---:|
| MAE | 9.46 | **3.87** | **3.08** |
| Bias | +9.37 | +2.33 | -0.73 |
| Correlation | 0.373 | 0.448 | 0.393 |

**Output tensor interface:**
```
density_map → [1, 104, 104, 1]  float32   Spatial density surface
```

**Count extraction (with threshold=0.15):**
```python
import numpy as np

raw = interpreter.get_tensor(output_details[0]["index"])  # (1, 104, 104, 1)
density_map = np.squeeze(raw).astype(np.float32)          # (104, 104)
threshold = 0.15 * density_map.max()                      # per-frame relative threshold
thresholded = np.where(density_map >= threshold, density_map, 0.0)
headcount = max(0, round(float(thresholded.sum())))
```

**Pi 3B runtime:** ~702 ms/frame (ai_edge_litert, XNNPACK, float32).

**⚠️ INT8 export:** Broken at runtime — XNNPack raises "failed to prepare" on `UpSampling2D(bilinear)` layers. Fix requires retraining decoder with `Conv2DTranspose`. Deferred.

---

### SECONDARY: `classcan_head_v1.tflite` (HUD bounding boxes only)

Custom Keras multi-scale MobileNetV3-Large + 416×416 head detector. For dashboard HUD overlay visualization only — does NOT drive headcount when the density model is loaded.

Export from epoch-60 MobileNetV3-Large checkpoint:
```bash
python scripts/export_to_tflite.py \
    --weights path/to/ckpt_ep60_v3.weights.h5 \
    --output  models/classcan_head_v1.tflite \
    --quant   float32
```

**Provenance:**
- Architecture: MobileNetV3-Large backbone + 3-scale FPN (52×52/26×26/13×13), occupancy-based overflow routing
- Dataset: 2,000 SCUT-HEAD Part A images + 35 local PCU-D classroom images (30°–50° ceiling angle)
- Best checkpoint: epoch 60 — val_loss=0.2535, Colab Drive: `/content/drive/MyDrive/models/`
- Tiled inference config (locked-in): 2×2 grid, 0.2 overlap, dual threshold (full=0.35, tile=0.65), Soft-NMS σ=0.5/t=0.3
- Validated metrics: P=31.3%, R=32.4%, F1=31.8%, MAE=3.84, r=0.986

**Output tensor interface (3-tensor, NMS applied inside TFLite graph):**
```
boxes  → [1, 100, 4]  float32   [ymin,xmin,ymax,xmax] normalized, zero-padded
scores → [1, 100]     float32   objectness scores, zero-padded
count  → [1]          int32     valid detection count (slice with [:count])
```

**Recommended conf_threshold:** 0.35 (set in `src/pi/config.py`)

---

### LEGACY SMOKE-TEST FALLBACK: `mobilenet_v2_ssd_classcan.tflite`

Stock COCO MobileNetV2-SSD model. Already present in this directory. Used automatically by `config.py` if neither density nor custom head model is found.

**⚠️ This model will badly undercount** in real classroom conditions: -65.2% bias (417 predicted vs ~1,200 GT across 30 images). Suitable only for verifying the camera→Pi→inference→dashboard plumbing works.

**Output format:** 4-tensor SSD (`boxes [1,N,4], classes [1,N], scores [1,N], num_detections [1]`)
**Recommended conf_threshold:** 0.50

---

## Quick-Start / Bench Testing

Download the stock COCO fallback model for pipeline smoke-testing:
```bash
python models/download_model.py
```

Smoke-test density model on a still image:
```bash
python scripts/run_on_image.py --image path/to/test.jpg --model models/classcan_density_float32.tflite
```

---

## Post-Export Tensor Inspection

### Density Model
```python
from ai_edge_litert.interpreter import Interpreter

interp = Interpreter("models/classcan_density_float32.tflite")
interp.allocate_tensors()

print("--- CLASSCAN Density Model ---")
for d in interp.get_input_details():
    print(f"  IN  shape={d['shape']}  dtype={d['dtype'].__name__}")
for d in interp.get_output_details():
    print(f"  OUT shape={d['shape']}  dtype={d['dtype'].__name__}")
```

Expected:
```
  IN  shape=[1, 416, 416, 3]   dtype=float32
  OUT shape=[1, 104, 104, 1]   dtype=float32
```

### Box Head Detector
```python
interp = Interpreter("models/classcan_head_v1.tflite")
interp.allocate_tensors()

print("--- CLASSCAN Head Detector ---")
for d in interp.get_input_details():
    print(f"  IN  shape={d['shape']}  dtype={d['dtype'].__name__}")
for d in interp.get_output_details():
    print(f"  OUT shape={d['shape']}  dtype={d['dtype'].__name__}  name={d['name']}")
```

Expected:
```
  IN  shape=[1, 416, 416, 3]  dtype=float32
  OUT shape=[1, 100, 4]       dtype=float32  name=boxes
  OUT shape=[1, 100]          dtype=float32  name=scores
  OUT shape=[1]               dtype=int32    name=count
```
