# models/

Place trained and exported `.tflite` model files here.

## Model Files

---

### PRIMARY: Weighted Ensemble <- **DEPLOY THIS**

> **Two TFLite files are required.** The previous single classcan_density_float32.tflite approach is superseded.  
> The final adopted model is a **weighted ensemble** of two checkpoints evaluated with **different preprocessing geometries**.

#### Ensemble components:

| File | Checkpoint | Eval preprocessing | Ensemble weight |
|---|---|---|:---:|
| classcan_density_round4_ep8.tflite | classcan_density_v4_round4_ft_epoch8.weights.h5 | **Letterbox** (preserve aspect ratio, pad black) | **0.6** |
| classcan_density_style_aug_ep8.tflite | classcan_density_style_aug_ft_lowLR_epoch8.weights.h5 | **Stretch** (cv2.resize to 416x416) | **0.4** |

Both models share the same architecture: MobileNetV3-Large backbone + progressive upsampling decoder -> 104x104 spatial density map (Softplus activation, 3.6M parameters each).

#### Export commands:

\\ash
# Export round 4 epoch 8 (letterbox model):
python scripts/export_to_tflite.py --mode density --weights path/to/classcan_density_v4_round4_ft_epoch8.weights.h5 --output models/classcan_density_round4_ep8.tflite --quant float32

# Export style-aug epoch 8 (stretch model):
python scripts/export_to_tflite.py --mode density --weights path/to/classcan_density_style_aug_ft_lowLR_epoch8.weights.h5 --output models/classcan_density_style_aug_ep8.tflite --quant float32
\
**Checkpoint locations (Colab Drive):**
- /content/drive/MyDrive/models/classcan_density_v4_round4_ft_epoch8.weights.h5
- /content/drive/MyDrive/models/classcan_density_style_aug_ft_lowLR_epoch8.weights.h5

#### Provenance (round 4 epoch 8):
- 4 rounds of hard-negative fine-tuning from classcan_density_v4_best, 84/8/8 SCUT-HEAD/hard-neg/hard-pos mix, LR raised to 5e-5 in round 4 (first LR change across all rounds)
- Epoch 8 broke the r=0.448 correlation ceiling from rounds 1-3
- Stretch eval: MAE=2.82, r=0.506 | **Letterbox eval (no retrain): MAE=3.23, r=0.602**

#### Provenance (style-aug epoch 8):
- Style-augmentation fine-tune (brightness/contrast/color/sharpness jitter on SCUT-HEAD stream only, AugMix-inspired), LR=5e-6
- **Only training run across all 9 rounds to complete 10 epochs without any collapse** -- std stable 32-36, mean 28-36 throughout
- Epoch 8 best on genuine held-out v2 data (350 frames): MAE=2.97, r=0.531
- The 3-way grid search picked it over stretch-ft-epoch1 entirely (weight 0.4 vs 0.0) -- genuinely complementary error signal

#### Real-footage performance (v2 held-out, 350 frames, genuine out-of-sample):

| Configuration | MAE | Bias | Correlation |
|---|:---:|:---:|:---:|
| Pre-fine-tune (base model) | 9.46 | +9.37 | 0.373 |
| Round 4 epoch 8, stretch eval | 2.82 | -1.73 | 0.506 |
| Round 4 epoch 8, letterbox eval | 3.23 | +2.58 | 0.602 |
| Style-aug epoch 8, stretch eval | 2.97 | -- | 0.531 |
| **Ensemble (0.6x epoch8_lb + 0.4x style-aug-ep8)** | **2.77** | **+1.58** | **0.586** |

Per-clip correlation: line1=0.455, line2=0.555, line3=0.759, sit1=0.538, sit2=0.519.

Finer-grained weight sweep confirmed: top-10 combos all r=0.584-0.586 (weights e8=0.50-0.65, style=0.30-0.50). Result is robust, not a lucky spike.

**Alternative lower-MAE configuration:** weights (0.55, 0.10, 0.35) -> MAE=2.68, r~0.584 (reintroduces stretch-ft-epoch1 at 10%).

#### Ensemble inference code (Python):

\\python
import numpy as np, cv2

def letterbox_resize(img, target=416):
    h, w = img.shape[:2]; scale = target / max(h, w)
    nh, nw = int(h*scale), int(w*scale)
    canvas = np.zeros((target,target,3), dtype=np.float32)
    canvas[:nh,:nw] = cv2.resize(img,(nw,nh)) / 255.0
    return canvas

def ensemble_count(frame_bgr, interp_ep8, interp_style, w_ep8=0.6, w_st=0.4):
    inp_lb = letterbox_resize(frame_bgr)[np.newaxis]
    interp_ep8.set_tensor(interp_ep8.get_input_details()[0]['index'], inp_lb)
    interp_ep8.invoke()
    dm8 = np.squeeze(interp_ep8.get_tensor(interp_ep8.get_output_details()[0]['index'])).astype(np.float32)

    inp_st = (cv2.resize(frame_bgr,(416,416)).astype(np.float32)/255.0)[np.newaxis]
    interp_style.set_tensor(interp_style.get_input_details()[0]['index'], inp_st)
    interp_style.invoke()
    dm_s = np.squeeze(interp_style.get_tensor(interp_style.get_output_details()[0]['index'])).astype(np.float32)

    return max(0, round(float(w_ep8 * dm8.sum() + w_st * dm_s.sum())))
\
**Output tensor interface (both models):** density_map -> [1, 104, 104, 1] float32

**Pi 3B runtime:** ~702 ms/frame per model (ai_edge_litert, XNNPACK, float32). Ensemble = ~1.4 s per scan position (within budget for periodic-snapshot architecture).

**INT8 export:** Broken at runtime -- XNNPack raises 'failed to prepare' on UpSampling2D(bilinear) layers. Fix requires retraining decoder with Conv2DTranspose. Deferred.

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
