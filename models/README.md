# models/

Place trained and quantized `.tflite` model files here.

Expected default model filename (configured in `src/pi/config.py`):
```
mobilenet_v2_ssd_classcan.tflite
```

---

## Quick-Start / Bench Testing

A pre-trained COCO MobileNetV2-SSD model can be downloaded automatically for smoke-testing:
```bash
python models/download_model.py
```

---

## Fine-Tuning & Training Pipeline

1. **Dataset Sources:**
   - **SCUT-HEAD Part A:** Academic benchmark dataset for head detection in crowded/classroom environments (academic-research-use license, sourced from original research repository).
   - **Local Classroom Dataset (35 Images):** High-resolution photos from Philippine public school classrooms taken at realistic ceiling pitch angles (30°–50° pitch) under varied lighting and furniture configurations.
2. **Annotation Convention:**
   - **Head-and-Shoulders Bounding Boxes:** Tight head-and-shoulder annotations instead of full-body boxes to resolve seated and partially desk-occluded students.
3. **Data Augmentation:**
   - Managed via Roboflow: Exposure/brightness shifts, perspective adjustments, scaling, and motion blur.
4. **Quantization & Export:**
   - Fine-tune MobileNetV2-SSD backbone.
   - Quantize to `uint8` with TFLite Converter for CPU-only inference on Cortex-A53.
   - Export to `models/mobilenet_v2_ssd_classcan.tflite`.
