# models/

Place trained and quantized `.tflite` model files here.

## Model Files

### Primary: `classcan_head_v1.tflite` ← **Export this to run the PoC**

Custom Keras multi-scale MobileNetV2 head detector.
**Must be generated from the epoch-55 checkpoint** using the export script:

```bash
python scripts/export_to_tflite.py \
    --weights path/to/ckpt_ep55.weights.h5 \
    --output  models/classcan_head_v1.tflite \
    --quant   float32
```

**Provenance:**
- Architecture: MobileNetV2 backbone + 3-scale FPN (P3/P4/P5), occupancy-based target encoding
- Dataset: 2,000 SCUT-HEAD Part A images + 35 local PCU-D classroom images (30°–50° ceiling angle)
- Training: 60 epochs total (50 base + 10 with box_loss_weight=2.0), Colab T4 GPU
- Best checkpoint: epoch 55 — val_loss=0.2519, Drive-verified (18,922,768 bytes)
- Inference result: 13/13 exact count match on validation image with NMS

**Output tensor interface (3-tensor, NMS already applied inside TFLite graph):**
```
boxes  → [1, 100, 4]  float32   [ymin,xmin,ymax,xmax] normalized, zero-padded
scores → [1, 100]     float32   objectness scores, zero-padded
count  → [1]          int32     valid detection count (slice with [:count])
```

**Recommended conf_threshold:** 0.35 (set in `src/pi/config.py`)

---

### Legacy / Smoke-Test Fallback: `mobilenet_v2_ssd_classcan.tflite`

Stock COCO MobileNetV2-SSD model. Already present in this directory.
Used automatically if `classcan_head_v1.tflite` is not found.

⚠️ **This model will undercount** in real classroom conditions — it fails on
desk-occluded distant rows (0 detections on the classroom wide-shot test case).
Suitable only for pipeline smoke-testing (verifying camera→Pi→inference→dashboard chain).

**Output format:** 4-tensor SSD (`boxes [1,N,4], classes [1,N], scores [1,N], num_detections [1]`)
**Recommended conf_threshold:** 0.50

---

## Quick-Start / Bench Testing

Download the stock COCO fallback model for pipeline smoke-testing:
```bash
python models/download_model.py
```

For end-to-end camera verification with the CLASSCAN model (after export):
```bash
python scripts/camera_verify.py --model models/classcan_head_v1.tflite --save
```

---

## Post-Export Tensor Inspection

After generating `classcan_head_v1.tflite`, verify the tensor signatures:

```python
from ai_edge_litert.interpreter import Interpreter

interp = Interpreter("models/classcan_head_v1.tflite")
interp.allocate_tensors()

print("--- CLASSCAN TFLite Model ---")
for d in interp.get_input_details():
    print(f"  IN  shape={d['shape']}  dtype={d['dtype'].__name__}")
for d in interp.get_output_details():
    print(f"  OUT shape={d['shape']}  dtype={d['dtype'].__name__}  name={d['name']}")
```

Expected output:
```
  IN  shape=[1, 300, 300, 3]  dtype=float32
  OUT shape=[1, 100, 4]  dtype=float32  name=...boxes
  OUT shape=[1, 100]     dtype=float32  name=...scores
  OUT shape=[1]          dtype=int32    name=...count
```

If `tf.image.non_max_suppression` fails to convert (requires `SELECT_TF_OPS`), add:
```python
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,
    tf.lite.OpsSet.SELECT_TF_OPS,
]
```
to `scripts/export_to_tflite.py` in the float32 branch.
