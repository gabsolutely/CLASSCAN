# CLASSCAN — Dataset Specification & Model Training Pipeline

This document defines the dataset composition, labeling standards, augmentation strategy, and quantization procedures for the CLASSCAN vision detection model.

---

## 1. Problem Definition & Architectural Objective

Standard object detection models (such as COCO-pretrained MobileNet-SSD or YOLO full-body models) fail when deployed in classroom settings because classroom furniture (wooden armchairs, shared tables, partition boards) physically obstructs 70% to 85% of a seated student's body.

```
                   [Ceiling Camera Angle: 30°–50°]
                                \
                                 ▼
                     ┌───────────────────────┐
                     │ Cranial Apex          │  <-- VISIBLE REGION
                     │ Neck & Shoulders Line │      (Annotated as "head")
                     ├───────────────────────┤
                     │ Torso & Arms          │  <-- PARTIALLY OCCLUDED
                     │ Desk / Armchair Wood  │      by classroom furniture
                     │ Legs & Feet           │  <-- FULLY OCCLUDED
                     └───────────────────────┘
```

**Target Objective:** Train an edge-optimized detector (**YOLOLite CPU Nano**) on a dedicated single **"head"** class (head-and-shoulders bounding boxes) to reliably detect seated students under severe furniture occlusion from an elevated perspective.

---

## 2. Dataset Composition

The training and evaluation corpus combines a large-scale academic benchmark with a localized classroom dataset:

| Dataset | Image Count | Resolution | Annotation Format | Description & Purpose | License / Source |
|---|:---:|:---:|:---:|---|---|
| **SCUT-HEAD (Part A)** | 2,000 | 1024×576 to 1920×1080 | Pascal VOC / YOLO TXT | Dense classroom and indoor surveillance scenes with high student density and overlapping heads. Provides broad feature diversity across seating patterns. | Academic Research License (SCUT) |
| **Local Classroom Dataset** | 35 | 3840×2160 (4K) | YOLO TXT (Roboflow) | High-resolution photographs captured inside Philippine Christian University – Dasmariñas (PCU-D) classrooms at realistic ceiling pitch angles ($30^\circ$–$50^\circ$), capturing local wooden armchairs, uniforms, and fluorescent/ambient sunlight variations. | Proprietary / In-House |

---

## 3. Annotation & Labeling Standard

All annotations are normalized to a single class:

```
Class Index: 0
Class Name:  "head"
```

### Bounding Box Boundary Rules:
1. **Top Boundary:** Apex of the head/hairline.
2. **Bottom Boundary:** The clavicle / lower shoulder line (the top contour of the chest where the neck joins the shoulders).
3. **Lateral Boundaries:** Outermost lateral span of the shoulders or hair.
4. **Occlusion Handling:** If a student's shoulders are partially blocked by a front seat, the bounding box encloses the visible head down to the highest visible obstruction boundary.
5. **Distance & Minimum Size:** All heads with a pixel height $\ge 12\text{ px}$ in the input frame are labeled.

---

## 4. Data Augmentation Strategy (Roboflow Pipeline)

To ensure model resilience against ambient lighting changes, camera lens distortions, and varied classroom layouts, the following augmentations are applied:

```
Raw Images (SCUT-HEAD + Local)
        │
        ├── 1. Exposure / Brightness Shifts (±25%)    --> Simulates morning sun vs. evening darkness
        ├── 2. Contrast Adjustments (±20%)            --> Simulates harsh fluorescent classroom lamps
        ├── 3. Horizontal Flip (50% probability)      --> Doubles perspective variation
        ├── 4. Perspective Warping (±10° pitch/yaw)   --> Simulates varied ceiling mounting angles
        ├── 5. Mild Gaussian Blur (up to 1.5 px)      --> Simulates slight camera vibration during sweep
        │
        ▼
Augmented Training Dataset (~5,500 total images)
```

---

## 5. Model Architecture & Training Hyperparameters

- **Base Architecture:** YOLOLite CPU (Nano) — lightweight single-stage anchor-based/anchor-free detector optimized for integer arithmetic on ARM Cortex CPUs.
- **Backbone:** ImageNet-pretrained lightweight depthwise separable convolution backbone.
- **Input Resolution:** $320 \times 320$ pixels (or $416 \times 416$ pixels for higher resolution on distant rows).
- **Batch Size:** 32 (on GPU training environment).
- **Epochs:** 150 epochs with Early Stopping (patience = 20).
- **Optimizer:** AdamW ($\text{lr} = 10^{-3}$, weight decay $= 10^{-4}$) with Cosine Annealing learning rate schedule.
- **Loss Function:** Complete IoU (CIoU) for bounding box regression + Binary Cross-Entropy (BCE) for head objectness.

---

## 6. Quantization & Export to TFLite

Following training convergence, the PyTorch model checkpoint is converted and quantized for CPU execution on the Raspberry Pi 3B:

### Quantization Commands & Conversion Script:

```python
import tensorflow as tf

# 1. Load trained SavedModel / Keras model
converter = tf.lite.TFLiteConverter.from_saved_model("exported_saved_model")

# 2. Enable Post-Training Quantization (PTQ)
converter.optimizations = [tf.lite.Optimize.DEFAULT]

# 3. Optional: Full Integer Quantization with representative dataset
def representative_data_gen():
    for input_value in representative_dataset_samples:
        yield [input_value.astype(np.float32)]

converter.representative_dataset = representative_data_gen
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.uint8
converter.inference_output_type = tf.uint8

# 4. Convert and save
tflite_model = converter.convert()
with open("models/yololite_nano_head_classcan.tflite", "wb") as f:
    f.write(tflite_model)
```

---

## 7. Model Signature Verification Checklist

Once the exported `.tflite` model is placed in `models/`, run the following validation snippet to verify tensor signatures:

```python
from ai_edge_litert.interpreter import Interpreter

interpreter = Interpreter(model_path="models/yololite_nano_head_classcan.tflite")
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print("--- TFLite Model Inspection ---")
print("Input Shape: ", input_details[0]["shape"])
print("Input Dtype: ", input_details[0]["dtype"])
print("Number of Output Tensors:", len(output_details))

for i, out in enumerate(output_details):
    print(f"Output {i}: Shape={out['shape']}, Dtype={out['dtype']}, Name={out['name']}")
```

### Expected Output Formats:
- **Standard 4-Tensor SSD Output:** `[boxes (1, N, 4), classes (1, N), scores (1, N), num_detections (1)]`
- **Combined YOLO Output:** `[predictions (1, N, 5 + num_classes)]` or `[predictions (1, N, 6)]` containing $[x_1, y_1, x_2, y_2, \text{score}, \text{class\_id}]$.
- The parser in `src/pi/detection/detector.py` automatically unpacks the verified tensor structure.
