# models/

Place trained and quantized `.tflite` model files here.

Target default model filename (configured in `src/pi/config.py`):
```
yololite_nano_head_classcan.tflite
```

Legacy / smoke-test fallback:
```
mobilenet_v2_ssd_classcan.tflite
```

---

## Quick-Start / Bench Testing

A pre-trained smoke-test model can be downloaded automatically for pipeline verification:
```bash
python models/download_model.py
```

---

## Fine-Tuning & Training Pipeline

1. **Architecture & Backbone:**
   - **YOLOLite CPU (Nano):** Extremely lightweight single-stage detector optimized for edge CPU inference without GPU acceleration.
   - **Backbone:** ImageNet-pretrained backbone for fast convergence and robust feature extraction.
2. **Dataset Sources:**
   - **SCUT-HEAD Part A (2,000 Images):** Academic benchmark dataset for head detection in classroom/surveillance environments (academic-research-use license, sourced from original research repository).
   - **Local Classroom Dataset (35 Images):** High-resolution photos from Philippine public school classrooms taken at realistic ceiling pitch angles (30°–50° pitch) capturing wooden armchairs, uniforms, and local lighting.
3. **Annotation Convention:**
   - **Single "head" Class:** Tight head-and-shoulders bounding boxes instead of full-body boxes to resolve seated and partially desk-occluded students.
4. **Data Augmentation (Roboflow):**
   - Exposure/brightness shifts, perspective adjustments, scale variation, and motion blur.
5. **Quantization & Export:**
   - Quantize to `uint8` / `float32` with TFLite Converter for CPU inference on Cortex-A53.
   - Export to `models/yololite_nano_head_classcan.tflite`.

---

## Post-Training Inspection Checklist

Once model training finishes and `.tflite` is exported:
1. Inspect input and output tensor details:
   ```python
   from ai_edge_litert.interpreter import Interpreter
   interp = Interpreter("models/yololite_nano_head_classcan.tflite")
   interp.allocate_tensors()
   print("Inputs:", interp.get_input_details())
   print("Outputs:", interp.get_output_details())
   ```
2. Verify output signature:
   - Check if output is a combined tensor (e.g. `[1, N, 6]` containing `[x1, y1, x2, y2, score, class_id]`) or separate tensors.
   - Determine if NMS (Non-Maximum Suppression) is built into the TFLite graph or requires post-processing in `detector.py`.
   - Confirm the class index for the single `"head"` class (typically `0`).
