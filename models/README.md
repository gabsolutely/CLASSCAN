# models/

Place trained and quantized `.tflite` model files here.

Expected filename (matches `config.py` default):
```
mobilenet_v2_ssd_classcan.tflite
```

## Training pipeline (planned)

1. Collect ceiling-angle classroom images (or use COCO person class as base)
2. Fine-tune MobileNetV2-SSD on classroom-specific data
3. Quantize to uint8 with TFLite converter
4. Drop `.tflite` output here and update `MODEL_PATH` in `src/pi/config.py`

A pre-trained COCO MobileNetV2-SSD can be used for initial bench-testing:
https://www.tensorflow.org/lite/examples/object_detection/overview
