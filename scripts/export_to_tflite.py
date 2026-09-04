"""
CLASSCAN — Keras Checkpoint → TFLite Export Script
====================================================
Converts the trained CLASSCAN Keras head-detector checkpoint (epoch-55 best)
to a TFLite model suitable for on-device inference on Raspberry Pi 3B.

Export Strategy (Option B — NMS wrapper baked in before export)
---------------------------------------------------------------
Rather than exporting the raw 6-tensor multi-scale output and doing all
post-processing in detector.py, this script wraps the Keras model in a
tf.Module that:
  1. Runs the multi-scale backbone + detection heads
  2. Applies sigmoid to all objectness logits
  3. Thresholds by a configurable objectness score
  4. Concatenates all surviving boxes and scores across P3/P4/P5
  5. Applies greedy IoU NMS

The TFLite model thus exposes a clean, simple interface to detector.py:
  Input:  [1, 300, 300, 3]  float32  (normalized 0..1 RGB image)
  Output: boxes  [1, MAX_DETECTIONS, 4]  float32  [ymin,xmin,ymax,xmax] normalized
          scores [1, MAX_DETECTIONS]     float32  objectness scores (0..1)
          count  [1]                     int32    number of valid detections

Boxes/scores beyond 'count' are zero-padded.

Usage
-----
  # Run locally (requires TF 2.x):
  python scripts/export_to_tflite.py \\
      --weights path/to/ckpt_ep55.weights.h5 \\
      --output  models/classcan_head_v1.tflite \\
      --quant   float32

  # With INT8 quantization (needs representative images dir):
  python scripts/export_to_tflite.py \\
      --weights path/to/ckpt_ep55.weights.h5 \\
      --output  models/classcan_head_v1.tflite \\
      --quant   int8 \\
      --rep-images path/to/representative_images/

After export, verify tensor signatures with the inspection block below, then
update src/pi/config.py MODEL_PATH to point to the new file.
"""

import argparse
import os
import sys
import numpy as np
import tensorflow as tf

# ─── Architecture constants (must match training) ─────────────────────────────
IMG_SIZE       = 300
GRID_SIZES     = {"P3": 38, "P4": 19, "P5": 10}
MAX_DETECTIONS = 100   # Pad/clip output to this many detections


# ─── 1. Rebuild Model Architecture ───────────────────────────────────────────
# (Must be identical to classcan_training_pipeline.py build_model())

def build_model() -> tf.keras.Model:
    """Reconstruct the CLASSCAN multi-scale head detector (load weights separately)."""
    inputs = tf.keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3), name="image_input")

    backbone = tf.keras.applications.MobileNetV2(
        input_shape=(IMG_SIZE, IMG_SIZE, 3),
        include_top=False,
        weights="imagenet",  # Placeholder — will be overwritten by load_weights
    )
    feat_p3 = backbone.get_layer("block_6_expand_relu").output
    feat_p4 = backbone.get_layer("block_13_expand_relu").output
    feat_p5 = backbone.get_layer("out_relu").output

    feat_model = tf.keras.Model(
        inputs=backbone.input,
        outputs=[feat_p3, feat_p4, feat_p5],
    )

    f3, f4, f5 = feat_model(inputs)

    def detection_head(feat, name_prefix: str):
        x = tf.keras.layers.Conv2D(
            128, 3, padding="same", activation="relu", name=f"{name_prefix}_conv"
        )(feat)
        obj = tf.keras.layers.Conv2D(
            1, 1, padding="same", name=f"{name_prefix}_obj"
        )(x)
        box = tf.keras.layers.Conv2D(
            4, 1, padding="same", activation="sigmoid", name=f"{name_prefix}_box"
        )(x)
        return obj, box

    obj3, box3 = detection_head(f3, "p3")
    obj4, box4 = detection_head(f4, "p4")
    obj5, box5 = detection_head(f5, "p5")

    return tf.keras.Model(
        inputs=inputs,
        outputs=[obj3, box3, obj4, box4, obj5, box5],
        name="classcan_head_detector",
    )


# ─── 2. NMS (numpy, for inference verification) ───────────────────────────────

def _iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    iy1 = np.maximum(box[0], boxes[:, 0])
    ix1 = np.maximum(box[1], boxes[:, 1])
    iy2 = np.minimum(box[2], boxes[:, 2])
    ix2 = np.minimum(box[3], boxes[:, 3])
    inter = np.maximum(0.0, iy2 - iy1) * np.maximum(0.0, ix2 - ix1)
    area_box = (box[2] - box[0]) * (box[3] - box[1])
    area_boxes = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / np.maximum(area_box + area_boxes - inter, 1e-6)


def numpy_nms(boxes: np.ndarray, scores: np.ndarray,
              iou_threshold: float = 0.45) -> list[int]:
    """Greedy IoU NMS — same logic as src/pi/detection/detector.py."""
    if len(boxes) == 0:
        return []
    order = np.argsort(scores)[::-1]
    kept = []
    while len(order):
        i = order[0]
        kept.append(int(i))
        order = order[1:]
        if not len(order):
            break
        ious = _iou(boxes[i], boxes[order])
        order = order[ious <= iou_threshold]
    return kept


# ─── 3. TF Export Wrapper ─────────────────────────────────────────────────────

class CLASSCANExportWrapper(tf.Module):
    """
    Wraps the Keras model with sigmoid + threshold + NMS post-processing
    so the exported TFLite model has a clean, fixed-shape output interface.

    Output tensors (all batched, batch dim = 1):
      boxes  [1, MAX_DETECTIONS, 4]  — [ymin,xmin,ymax,xmax] normalized, zero-padded
      scores [1, MAX_DETECTIONS]     — objectness scores, zero-padded
      count  [1]                     — number of valid detections (use [:count] to slice)
    """

    def __init__(self, keras_model: tf.keras.Model,
                 obj_threshold: float = 0.35,
                 nms_iou_threshold: float = 0.45,
                 max_detections: int = MAX_DETECTIONS):
        super().__init__()
        self.model = keras_model
        self.obj_threshold = obj_threshold
        self.nms_iou_threshold = nms_iou_threshold
        self.max_det = max_detections

    @tf.function(input_signature=[
        tf.TensorSpec(shape=[1, IMG_SIZE, IMG_SIZE, 3], dtype=tf.float32, name="image")
    ])
    def detect(self, image: tf.Tensor):
        """Full inference: backbone → heads → sigmoid → NMS → fixed-size output."""
        obj3, box3, obj4, box4, obj5, box5 = self.model(image, training=False)

        all_boxes_list  = []
        all_scores_list = []

        for obj_map, box_map in [(obj3, box3), (obj4, box4), (obj5, box5)]:
            scores = tf.sigmoid(obj_map[0, :, :, 0])  # (H, W)
            boxes  = box_map[0]                         # (H, W, 4)

            # Flatten and threshold
            flat_scores = tf.reshape(scores, [-1])
            flat_boxes  = tf.reshape(boxes,  [-1, 4])

            mask = flat_scores >= self.obj_threshold
            sel_scores = tf.boolean_mask(flat_scores, mask)
            sel_boxes  = tf.boolean_mask(flat_boxes,  mask)

            all_scores_list.append(sel_scores)
            all_boxes_list.append(sel_boxes)

        all_scores = tf.concat(all_scores_list, axis=0)  # (K,)
        all_boxes  = tf.concat(all_boxes_list,  axis=0)  # (K, 4)

        # NMS via TF built-in (handles dynamic K cleanly in TFLite graph)
        # Note: tf.image.non_max_suppression expects [y1,x1,y2,x2] — matches our format
        nms_indices = tf.image.non_max_suppression(
            all_boxes,
            all_scores,
            max_output_size=self.max_det,
            iou_threshold=self.nms_iou_threshold,
            score_threshold=float("-inf"),  # Already pre-filtered
        )

        kept_boxes  = tf.gather(all_boxes,  nms_indices)  # (n_kept, 4)
        kept_scores = tf.gather(all_scores, nms_indices)  # (n_kept,)
        count       = tf.shape(nms_indices)[0]            # scalar

        # Pad to fixed MAX_DETECTIONS for TFLite fixed-shape output
        pad_boxes  = tf.zeros([self.max_det, 4], dtype=tf.float32)
        pad_scores = tf.zeros([self.max_det],    dtype=tf.float32)

        pad_boxes  = tf.tensor_scatter_nd_update(
            pad_boxes,  tf.expand_dims(tf.range(count), 1), kept_boxes
        )
        pad_scores = tf.tensor_scatter_nd_update(
            pad_scores, tf.expand_dims(tf.range(count), 1), kept_scores
        )

        # Add batch dimension
        out_boxes  = tf.expand_dims(pad_boxes,  0)           # [1, MAX, 4]
        out_scores = tf.expand_dims(pad_scores, 0)           # [1, MAX]
        out_count  = tf.expand_dims(tf.cast(count, tf.int32), 0)  # [1]

        return {"boxes": out_boxes, "scores": out_scores, "count": out_count}


# ─── 4. Export to TFLite ─────────────────────────────────────────────────────

def export_classcan_model(
    weights_path: str,
    output_path: str = "models/classcan_head_v1.tflite",
    quantization: str = "float32",
    representative_images_dir: str | None = None,
    obj_threshold: float = 0.35,
    nms_iou_threshold: float = 0.45,
) -> str:
    """
    Load Keras checkpoint, wrap with NMS module, convert to TFLite.

    Args:
        weights_path:              Path to .weights.h5 checkpoint (epoch-55 best)
        output_path:               Destination .tflite file path
        quantization:              "float32" or "int8"
        representative_images_dir: Directory of .jpg/.png images for INT8 calibration
        obj_threshold:             Score threshold baked into export wrapper
        nms_iou_threshold:         NMS IoU threshold baked into export wrapper

    Returns:
        output_path (str)
    """
    print("=" * 60)
    print("  CLASSCAN TFLite Export")
    print("=" * 60)

    # 4a. Build model and load weights
    print(f"\n[1/4] Building model architecture...")
    model = build_model()
    print(f"      Parameters: {model.count_params():,}")

    print(f"\n[2/4] Loading weights from: {weights_path}")
    model.load_weights(weights_path)
    print("      Weights loaded.")

    # 4b. Wrap with export module
    print(f"\n[3/4] Wrapping with NMS export module...")
    wrapper = CLASSCANExportWrapper(
        keras_model=model,
        obj_threshold=obj_threshold,
        nms_iou_threshold=nms_iou_threshold,
        max_detections=MAX_DETECTIONS,
    )

    # 4c. Convert to TFLite
    print(f"\n[4/4] Converting to TFLite ({quantization})...")
    converter = tf.lite.TFLiteConverter.from_concrete_functions(
        [wrapper.detect.get_concrete_function()],
        wrapper,
    )

    if quantization == "int8":
        if representative_images_dir is None:
            raise ValueError(
                "INT8 quantization requires --rep-images path to a directory of "
                "representative images (JPG/PNG, 300×300 or larger)."
            )

        import glob
        image_files = (
            glob.glob(os.path.join(representative_images_dir, "*.jpg")) +
            glob.glob(os.path.join(representative_images_dir, "*.png"))
        )
        if not image_files:
            raise ValueError(
                f"No .jpg/.png images found in: {representative_images_dir}"
            )
        print(f"      Using {len(image_files)} representative images for INT8 calibration.")

        def representative_data_gen():
            for img_path in image_files[:200]:  # Cap at 200 for speed
                img = tf.io.read_file(img_path)
                img = tf.io.decode_image(img, channels=3, expand_animations=False)
                img = tf.image.resize(img, [IMG_SIZE, IMG_SIZE])
                img = tf.cast(img, tf.float32) / 255.0
                img = tf.expand_dims(img, 0)
                yield [img]

        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = representative_data_gen
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type  = tf.float32  # Keep float input for Pi ease
        converter.inference_output_type = tf.float32

    elif quantization == "float32":
        # No quantization — largest file, easiest to debug on Pi
        pass

    else:
        raise ValueError(f"Unknown quantization mode: {quantization}. Use 'float32' or 'int8'.")

    tflite_model = converter.convert()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(tflite_model)

    size_mb = len(tflite_model) / 1024 / 1024
    print(f"\n[✓] TFLite model saved: {output_path}")
    print(f"    File size: {size_mb:.2f} MB")

    # 4d. Verify tensor signatures
    _print_tflite_signature(output_path)
    return output_path


def _print_tflite_signature(tflite_path: str):
    """Print input/output tensor details for the exported TFLite model."""
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tflite_runtime.interpreter import Interpreter
        except ImportError:
            from tensorflow.lite.python.interpreter import Interpreter

    interpreter = Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()

    print("\n--- TFLite Model Tensor Inspection ---")
    for d in interpreter.get_input_details():
        print(f"  INPUT  [{d['index']}] {d['name']:40s} shape={d['shape']}  dtype={d['dtype'].__name__}")
    for d in interpreter.get_output_details():
        print(f"  OUTPUT [{d['index']}] {d['name']:40s} shape={d['shape']}  dtype={d['dtype'].__name__}")
    print()
    print("Expected output names and shapes:")
    print("  boxes  → [1, 100, 4]  float32  (zero-padded, use [:count])")
    print("  scores → [1, 100]     float32  (zero-padded, use [:count])")
    print("  count  → [1]          int32    (number of valid detections)")


# ─── 5. CLI Entry Point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export CLASSCAN Keras checkpoint to TFLite"
    )
    parser.add_argument(
        "--weights", required=True,
        help="Path to .weights.h5 checkpoint (e.g. ckpt_ep55.weights.h5)"
    )
    parser.add_argument(
        "--output", default="models/classcan_head_v1.tflite",
        help="Output .tflite file path (default: models/classcan_head_v1.tflite)"
    )
    parser.add_argument(
        "--quant", choices=["float32", "int8"], default="float32",
        help="Quantization mode (default: float32)"
    )
    parser.add_argument(
        "--rep-images",
        help="Directory of representative images for INT8 calibration (required for --quant int8)"
    )
    parser.add_argument(
        "--obj-threshold", type=float, default=0.35,
        help="Objectness score threshold baked into the export wrapper (default: 0.35)"
    )
    parser.add_argument(
        "--nms-iou", type=float, default=0.45,
        help="NMS IoU threshold baked into the export wrapper (default: 0.45)"
    )
    args = parser.parse_args()

    export_classcan_model(
        weights_path=args.weights,
        output_path=args.output,
        quantization=args.quant,
        representative_images_dir=args.rep_images,
        obj_threshold=args.obj_threshold,
        nms_iou_threshold=args.nms_iou,
    )
