"""
CLASSCAN — Consolidated Keras/TF Training Pipeline
====================================================
Run this notebook-style script in Google Colab (GPU runtime).

Architecture
------------
  MobileNetV2 backbone (300×300, ImageNet weights)
  3 detection heads off:
    • P3: block_6_expand_relu  → 38×38 grid, stride 8
    • P4: block_13_expand_relu → 19×19 grid, stride 16
    • P5: out_relu             → 10×10 grid, stride 32
  Each head: Conv2D(128,3,padding='same') → objectness (1 ch) + box regression (4 ch)

Target Encoding
---------------
  Occupancy-based overflow routing (NOT size-gated, since ALL boxes in this
  dataset have max(h,w) <= 0.07 — no scale variety, so size routing gives
  zero signal on P4/P5).

  For each box: place center cell in P3. If cell occupied, overflow to P4.
  If still occupied, overflow to P5. Drops box only if all three are full
  (extremely rare at crowd densities this dataset contains).

  This repurposes multi-scale to solve the dense-crowd collision problem:
  a single 38×38 grid can only hold 1 box per cell, so nearby heads would
  silently overwrite each other. Overflow routing eliminates that loss.

  Verified on a 83-box training image: P3=69, P4=11, P5=3, 0 drops.

Loss
----
  Focal loss (alpha=0.25, gamma=2.0, from_logits=True) for objectness.
  Smooth-L1 for box regression (masked to positive cells only).
  Normalized by positive cell count, summed across all 3 scales.
  box_loss_weight configurable (trained 1.0 → bumped to 2.0 at epoch 51).

  CRITICAL: use from_logits=True — manual sigmoid + log(p) is numerically
  unstable (saturating sigmoid → log(0) → NaN). Confirmed root cause of
  original NaN training failures.

NaN Recovery Protocol (banked lesson)
--------------------------------------
  Any time a NaN loss appears during training:
  (a) diagnose and fix the actual code bug,
  (b) ALWAYS rebuild BOTH model and optimizer from scratch before retrying.
  A single bad gradient step permanently corrupts model weights AND Adam's
  internal momentum state. No downstream code fix will produce finite loss
  on a corrupted model. See: _rebuild_model_and_optimizer().

Checkpoint Safety
-----------------
  save_checkpoint_verified() asserts the Drive file actually exists and
  matches byte size before trusting it. This was added after the 63-epoch
  checkpoint loss disaster (silent Drive save failures due to account/session
  mismatch across notebook tabs).

Usage
-----
  1. Set DRIVE_CHECKPOINT_DIR to a valid folder on your Drive.
  2. Run cells top-to-bottom. If resuming: set RESUME_FROM_CHECKPOINT.
  3. After training: run the export section to produce classcan_head_v1.tflite.

Training History (for reference)
---------------------------------
  Run 1 (original account, lost):
    63 epochs, checkpoint save silently failed → weights lost on runtime disconnect.
  Run 2 (brother's laptop/account, hardened script):
    50 epochs: smooth monotonic decrease, val plateau reached at ~epoch 47-50.
    Checkpoints epochs 5/10/15/20/25/30/35/40/45/50 verified (18922768 bytes each).
    Epoch 50 inference+NMS: 13/13 exact count match on val image.
  Run 3 (box_loss_weight bumped to 2.0, continuing from epoch 50):
    15 more epochs (51-65). val bottomed at epoch 55, started rising by 60.
    Best checkpoint: epoch 55.
"""

# ─── 0. Imports & Drive Setup ────────────────────────────────────────────────

import os
import math
import time
import numpy as np
import tensorflow as tf

# Mount Drive (Colab only — comment out if running locally)
from google.colab import drive
drive.mount("/content/drive")

# ─── 1. Configuration ────────────────────────────────────────────────────────

DRIVE_CHECKPOINT_DIR = "/content/drive/MyDrive/CLASSCAN_checkpoints"  # ← SET THIS
RESUME_FROM_CHECKPOINT = None  # e.g. "/content/drive/MyDrive/CLASSCAN_checkpoints/ckpt_ep50.weights.h5"

DATASET_ROOT = "/content/CLASSCAN-1"  # Roboflow export root (re-download each fresh runtime)
TRAIN_TFRECORD = os.path.join(DATASET_ROOT, "train", "CLASSCAN.tfrecord")
VALID_TFRECORD = os.path.join(DATASET_ROOT, "valid", "CLASSCAN.tfrecord")
LABEL_MAP_PATH = os.path.join(DATASET_ROOT, "train", "CLASSCAN_label_map.pbtxt")
# Note: label map shows class name "person" with id 1 — this is a cosmetic Roboflow
# naming artifact. The class IS head detection. No relabeling needed.

IMG_SIZE       = 300
BATCH_SIZE     = 8
LEARNING_RATE  = 1e-5
CLIPNORM       = 1.0
START_EPOCH    = 1         # Set to (resume_epoch + 1) when resuming
NUM_EPOCHS     = 30        # Additional epochs from START_EPOCH
SAVE_EVERY     = 5         # Save checkpoint every N epochs
BOX_LOSS_WEIGHT = 1.0      # Set to 2.0 for tightness fine-tuning phase (post-epoch 50)

# Detection head grid sizes (must match backbone strides)
GRID_SIZES = {
    "P3": 38,  # stride 8  — block_6_expand_relu
    "P4": 19,  # stride 16 — block_13_expand_relu
    "P5": 10,  # stride 32 — out_relu
}

# ─── 2. Drive Checkpoint Directory Verification ──────────────────────────────

print("=" * 60)
print("  CLASSCAN Training Pipeline — Startup Checks")
print("=" * 60)

os.makedirs(DRIVE_CHECKPOINT_DIR, exist_ok=True)

# Critical: verify we can actually write to Drive before starting training
_test_file = os.path.join(DRIVE_CHECKPOINT_DIR, "_write_test.tmp")
try:
    with open(_test_file, "w") as f:
        f.write("write_test")
    assert os.path.isfile(_test_file), "Drive write test file not visible after write!"
    os.remove(_test_file)
    print(f"[✓] Drive write test passed: {DRIVE_CHECKPOINT_DIR}")
except Exception as e:
    raise RuntimeError(
        f"[✗] Drive write test FAILED at {DRIVE_CHECKPOINT_DIR}\n"
        f"    Check: is Drive mounted? Is the path correct? Is the account right?\n"
        f"    Error: {e}"
    )

print(f"[✓] GPU available: {tf.config.list_physical_devices('GPU')}")
print()

# ─── 3. TFRecord Parsing ─────────────────────────────────────────────────────

FEATURE_SPEC = {
    "image/height":           tf.io.FixedLenFeature([], tf.int64),
    "image/width":            tf.io.FixedLenFeature([], tf.int64),
    "image/encoded":          tf.io.FixedLenFeature([], tf.string),
    "image/object/bbox/ymin": tf.io.VarLenFeature(tf.float32),
    "image/object/bbox/xmin": tf.io.VarLenFeature(tf.float32),
    "image/object/bbox/ymax": tf.io.VarLenFeature(tf.float32),
    "image/object/bbox/xmax": tf.io.VarLenFeature(tf.float32),
}


def parse_tfrecord(example_proto):
    """Parse one TFRecord example into (image_tensor, boxes_tensor)."""
    feat = tf.io.parse_single_example(example_proto, FEATURE_SPEC)

    image = tf.io.decode_jpeg(feat["image/encoded"], channels=3)
    image = tf.image.resize(image, [IMG_SIZE, IMG_SIZE])
    image = tf.cast(image, tf.float32) / 255.0  # Normalize to [0, 1]

    ymin = tf.sparse.to_dense(feat["image/object/bbox/ymin"])
    xmin = tf.sparse.to_dense(feat["image/object/bbox/xmin"])
    ymax = tf.sparse.to_dense(feat["image/object/bbox/ymax"])
    xmax = tf.sparse.to_dense(feat["image/object/bbox/xmax"])
    boxes = tf.stack([ymin, xmin, ymax, xmax], axis=1)  # (N, 4)

    return image, boxes


# ─── 4. Occupancy-Based Target Encoder ───────────────────────────────────────

def encode_targets(image, boxes):
    """
    tf.py_function wrapper around numpy-level target encoding.

    Occupancy-based overflow routing:
      Each box's center is mapped to P3 first. If the cell is occupied,
      it overflows to P4, then P5. This prevents dense-crowd cell collisions
      (multiple nearby head centers sharing the same grid cell) that silently
      lost detections under the old size-gated routing.

    Args:
        image: (H, W, 3) float32 — passed through unchanged
        boxes: (N, 4) float32 — [ymin, xmin, ymax, xmax] normalized 0..1

    Returns:
        image: unchanged
        obj3, box3: (38, 38, 1), (38, 38, 4) targets for P3
        obj4, box4: (19, 19, 1), (19, 19, 4) targets for P4
        obj5, box5: (10, 10, 1), (10, 10, 4) targets for P5
    """
    # CRITICAL: convert to numpy before iterating — tf.py_function wraps
    # tensors as EagerTensors, and iterating over them as arrays causes
    # crashes on empty boxes (images with 0 annotations).
    boxes_np = boxes.numpy()  # (N, 4)

    g3, g4, g5 = GRID_SIZES["P3"], GRID_SIZES["P4"], GRID_SIZES["P5"]

    obj3 = np.zeros((g3, g3, 1), dtype=np.float32)
    box3 = np.zeros((g3, g3, 4), dtype=np.float32)
    obj4 = np.zeros((g4, g4, 1), dtype=np.float32)
    box4 = np.zeros((g4, g4, 4), dtype=np.float32)
    obj5 = np.zeros((g5, g5, 1), dtype=np.float32)
    box5 = np.zeros((g5, g5, 4), dtype=np.float32)

    for box in boxes_np:
        ymin, xmin, ymax, xmax = box
        cy = (ymin + ymax) / 2.0
        cx = (xmin + xmax) / 2.0

        # Try P3
        r3, c3 = int(cy * g3), int(cx * g3)
        r3 = min(r3, g3 - 1)
        c3 = min(c3, g3 - 1)
        if obj3[r3, c3, 0] == 0:
            obj3[r3, c3, 0] = 1.0
            box3[r3, c3] = box
            continue

        # Overflow to P4
        r4, c4 = int(cy * g4), int(cx * g4)
        r4 = min(r4, g4 - 1)
        c4 = min(c4, g4 - 1)
        if obj4[r4, c4, 0] == 0:
            obj4[r4, c4, 0] = 1.0
            box4[r4, c4] = box
            continue

        # Overflow to P5
        r5, c5 = int(cy * g5), int(cx * g5)
        r5 = min(r5, g5 - 1)
        c5 = min(c5, g5 - 1)
        if obj5[r5, c5, 0] == 0:
            obj5[r5, c5, 0] = 1.0
            box5[r5, c5] = box
        # else: all scales full for this box — extremely rare, silently dropped

    return image, obj3, box3, obj4, box4, obj5, box5


def encode_targets_wrapper(image, boxes):
    """Wrap encode_targets for tf.py_function (handles tensor ↔ numpy boundary)."""
    results = tf.py_function(
        func=encode_targets,
        inp=[image, boxes],
        Tout=[tf.float32, tf.float32, tf.float32,
              tf.float32, tf.float32, tf.float32, tf.float32],
    )
    g3, g4, g5 = GRID_SIZES["P3"], GRID_SIZES["P4"], GRID_SIZES["P5"]
    results[0].set_shape([IMG_SIZE, IMG_SIZE, 3])
    results[1].set_shape([g3, g3, 1])
    results[2].set_shape([g3, g3, 4])
    results[3].set_shape([g4, g4, 1])
    results[4].set_shape([g4, g4, 4])
    results[5].set_shape([g5, g5, 1])
    results[6].set_shape([g5, g5, 4])
    return tuple(results)


# ─── 5. tf.data Pipeline ─────────────────────────────────────────────────────

def build_dataset(tfrecord_path: str, shuffle: bool = False):
    """Build a batched, prefetched tf.data dataset from a TFRecord file."""
    ds = tf.data.TFRecordDataset(tfrecord_path)
    ds = ds.map(parse_tfrecord, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.map(encode_targets_wrapper, num_parallel_calls=tf.data.AUTOTUNE)
    if shuffle:
        ds = ds.shuffle(buffer_size=512, reshuffle_each_iteration=True)
    ds = ds.batch(BATCH_SIZE, drop_remainder=False)
    ds = ds.prefetch(tf.data.AUTOTUNE)
    return ds


# NOTE: Build datasets AFTER any function changes. Redefining a function in a
# new cell does NOT retroactively update an already-built tf.data pipeline.
# Always rebuild the pipeline from this cell downward after any function edit.
train_ds = build_dataset(TRAIN_TFRECORD, shuffle=True)
valid_ds = build_dataset(VALID_TFRECORD, shuffle=False)

print(f"[✓] Datasets built — batch_size={BATCH_SIZE}")

# ─── 6. Model Architecture ───────────────────────────────────────────────────

def build_model():
    """
    Multi-scale head detector on MobileNetV2 backbone.

    Backbone: MobileNetV2 (300×300 input, ImageNet weights, non-trainable initially)
    3 detection heads:
      P3 — block_6_expand_relu  (38×38, stride 8)
      P4 — block_13_expand_relu (19×19, stride 16)
      P5 — out_relu             (10×10, stride 32)

    Each head: Conv2D(128, 3×3, ReLU) → split to:
      objectness_N  (Conv2D, 1 ch, linear — trained with from_logits focal loss)
      boxes_N       (Conv2D, 4 ch, sigmoid — normalized [ymin,xmin,ymax,xmax])

    ~4.6M total params.
    """
    inputs = tf.keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3), name="image_input")

    backbone = tf.keras.applications.MobileNetV2(
        input_shape=(IMG_SIZE, IMG_SIZE, 3),
        include_top=False,
        weights="imagenet",
    )
    backbone.trainable = True  # Fine-tune backbone (set False for frozen backbone runs)

    # Extract feature maps at 3 scales
    feat_p3 = backbone.get_layer("block_6_expand_relu").output   # 38×38
    feat_p4 = backbone.get_layer("block_13_expand_relu").output  # 19×19
    feat_p5 = backbone.get_layer("out_relu").output              # 10×10

    feat_model = tf.keras.Model(
        inputs=backbone.input,
        outputs=[feat_p3, feat_p4, feat_p5],
    )

    f3, f4, f5 = feat_model(inputs)

    def detection_head(feat, grid_size: int, name_prefix: str):
        """Shared detection head structure applied at each scale."""
        x = tf.keras.layers.Conv2D(
            128, 3, padding="same", activation="relu", name=f"{name_prefix}_conv"
        )(feat)
        obj = tf.keras.layers.Conv2D(
            1, 1, padding="same", name=f"{name_prefix}_obj"
        )(x)  # Logits — no activation (from_logits focal loss)
        box = tf.keras.layers.Conv2D(
            4, 1, padding="same", activation="sigmoid", name=f"{name_prefix}_box"
        )(x)  # Sigmoid → normalized [0,1] coordinates
        return obj, box

    obj3, box3 = detection_head(f3, GRID_SIZES["P3"], "p3")
    obj4, box4 = detection_head(f4, GRID_SIZES["P4"], "p4")
    obj5, box5 = detection_head(f5, GRID_SIZES["P5"], "p5")

    model = tf.keras.Model(
        inputs=inputs,
        outputs=[obj3, box3, obj4, box4, obj5, box5],
        name="classcan_head_detector",
    )
    return model


# ─── 7. Loss Functions ───────────────────────────────────────────────────────

def focal_loss(y_true, y_pred_logits, alpha: float = 0.25, gamma: float = 2.0):
    """
    Focal loss for objectness, operating on raw logits (numerically stable).

    CRITICAL: Do NOT pass sigmoid-ed probabilities here. Use from_logits=True
    in BinaryCrossentropy. Manual sigmoid + log(p) is numerically unstable
    (saturating sigmoid → log(0) → NaN). This was the root cause of the
    original NaN training failures.
    """
    bce = tf.keras.losses.BinaryCrossentropy(from_logits=True, reduction="none")
    ce = bce(y_true, y_pred_logits)

    p = tf.sigmoid(y_pred_logits)
    p_t = tf.where(tf.cast(y_true, tf.bool), p, 1.0 - p)
    p_t = tf.clip_by_value(p_t, 1e-7, 1.0 - 1e-7)  # Prevent log(0) edge cases

    alpha_t = tf.where(tf.cast(y_true, tf.bool), alpha, 1.0 - alpha)
    focal_weight = alpha_t * tf.pow(1.0 - p_t, gamma)

    return focal_weight * ce


def smooth_l1_loss(y_true, y_pred, delta: float = 1.0):
    """Smooth-L1 (Huber) loss for box regression."""
    diff = tf.abs(y_true - y_pred)
    return tf.where(diff < delta, 0.5 * diff ** 2, delta * (diff - 0.5 * delta))


def compute_loss(model_outputs, targets, box_loss_weight: float = 1.0):
    """
    Compute total detection loss across all 3 scales.

    Args:
        model_outputs: (obj3, box3, obj4, box4, obj5, box5) — raw model outputs per batch
        targets:       (obj3_t, box3_t, obj4_t, box4_t, obj5_t, box5_t) — ground truth
        box_loss_weight: multiplier on box regression loss (default 1.0; set 2.0 for tightness)

    Returns:
        total_loss, obj_loss, box_loss (all scalar tensors)
    """
    pred_obj3, pred_box3, pred_obj4, pred_box4, pred_obj5, pred_box5 = model_outputs
    tgt_obj3, tgt_box3, tgt_obj4, tgt_box4, tgt_obj5, tgt_box5 = targets

    total_obj = 0.0
    total_box = 0.0
    total_pos = tf.constant(0.0)

    for pred_obj, pred_box, tgt_obj, tgt_box in [
        (pred_obj3, pred_box3, tgt_obj3, tgt_box3),
        (pred_obj4, pred_box4, tgt_obj4, tgt_box4),
        (pred_obj5, pred_box5, tgt_obj5, tgt_box5),
    ]:
        obj_loss_map = focal_loss(tgt_obj, pred_obj)
        total_obj += tf.reduce_sum(obj_loss_map)

        pos_mask = tf.cast(tgt_obj > 0, tf.float32)  # (B, H, W, 1)
        pos_mask_4 = tf.repeat(pos_mask, 4, axis=-1)  # (B, H, W, 4)
        box_loss_map = smooth_l1_loss(tgt_box, pred_box) * pos_mask_4
        total_box += tf.reduce_sum(box_loss_map)
        total_pos += tf.reduce_sum(pos_mask)

    # Normalize by positive cell count (add eps to avoid division by zero)
    norm = tf.maximum(total_pos, 1.0)
    obj_loss = total_obj / norm
    box_loss = total_box / norm
    total_loss = obj_loss + box_loss_weight * box_loss

    return total_loss, obj_loss, box_loss


# ─── 8. Training & Eval Steps ────────────────────────────────────────────────

# NOTE: @tf.function traces are cached on the Python function object.
# Redefining train_step in a new cell does NOT update the cached trace used
# by the tf.data pipeline. Always re-run THIS cell (and the dataset build
# cell) after any function change. This bit us 3 times during development.

@tf.function
def train_step(batch, model, optimizer, box_loss_weight):
    image_batch, obj3_t, box3_t, obj4_t, box4_t, obj5_t, box5_t = batch
    targets = (obj3_t, box3_t, obj4_t, box4_t, obj5_t, box5_t)
    with tf.GradientTape() as tape:
        outputs = model(image_batch, training=True)
        loss, obj_l, box_l = compute_loss(outputs, targets, box_loss_weight)
    grads = tape.gradient(loss, model.trainable_variables)
    optimizer.apply_gradients(zip(grads, model.trainable_variables))
    return loss, obj_l, box_l


@tf.function
def eval_step(batch, model, box_loss_weight):
    image_batch, obj3_t, box3_t, obj4_t, box4_t, obj5_t, box5_t = batch
    targets = (obj3_t, box3_t, obj4_t, box4_t, obj5_t, box5_t)
    outputs = model(image_batch, training=False)
    loss, obj_l, box_l = compute_loss(outputs, targets, box_loss_weight)
    return loss, obj_l, box_l


# ─── 9. Checkpoint Helper ────────────────────────────────────────────────────

def save_checkpoint_verified(model, epoch: int) -> str:
    """
    Save model weights to Drive and verify the file actually exists and
    has the expected byte count before returning.

    This was added after the 63-epoch checkpoint loss disaster: Drive saves
    silently failed (folder never existed on the actual account checked,
    likely account/session mismatch across notebook tabs). Without this
    guard, a runtime disconnect after silent-fail = total training loss.

    Raises RuntimeError if the file is not found or is suspiciously small.
    """
    path = os.path.join(DRIVE_CHECKPOINT_DIR, f"ckpt_ep{epoch:02d}.weights.h5")
    model.save_weights(path)

    if not os.path.isfile(path):
        raise RuntimeError(
            f"[✗] Checkpoint save FAILED — file not found after save_weights()!\n"
            f"    Path: {path}\n"
            f"    Check Drive mount and account match."
        )

    size_bytes = os.path.getsize(path)
    if size_bytes < 1_000_000:  # Sanity: weights file should be >1 MB
        raise RuntimeError(
            f"[✗] Checkpoint suspiciously small ({size_bytes} bytes): {path}\n"
            f"    Expected >1 MB. Save may have partially failed."
        )

    print(f"[✓] Checkpoint saved & verified: {path} ({size_bytes:,} bytes)")
    return path


# ─── 10. NaN Recovery Helper ─────────────────────────────────────────────────

def _rebuild_model_and_optimizer(learning_rate=LEARNING_RATE, clipnorm=CLIPNORM):
    """
    Rebuild both model and optimizer from scratch.

    CRITICAL: Call this after ANY run that produces NaN loss, even if you
    believe you've fixed the code bug. A single bad gradient step permanently
    corrupts model weights AND Adam's internal momentum/variance accumulators.
    No amount of downstream code fixing will produce finite loss again on a
    corrupted model+optimizer pair.

    Recovery order:
      (a) Diagnose and fix the actual code bug.
      (b) Call this function to get clean model + optimizer.
      (c) Retry training.
    """
    print("[!] Rebuilding model and optimizer from scratch...")
    model = build_model()
    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate, clipnorm=clipnorm)
    print("[✓] Fresh model and optimizer ready.")
    return model, optimizer


# ─── 11. Main Training Loop ──────────────────────────────────────────────────

# Build initial model and optimizer
model, optimizer = _rebuild_model_and_optimizer()

# Resume from checkpoint if specified
if RESUME_FROM_CHECKPOINT:
    print(f"[→] Resuming from checkpoint: {RESUME_FROM_CHECKPOINT}")
    model.load_weights(RESUME_FROM_CHECKPOINT)
    print("[✓] Weights loaded.")
else:
    print("[→] Training from scratch (no resume checkpoint set).")

print(f"\nModel parameters: {model.count_params():,}")
print(f"Training {NUM_EPOCHS} epoch(s) from epoch {START_EPOCH}")
print(f"Box loss weight: {BOX_LOSS_WEIGHT}")
print()

history = {"train_loss": [], "val_loss": []}

for epoch in range(START_EPOCH, START_EPOCH + NUM_EPOCHS):
    epoch_start = time.time()

    # ── Training phase ────────────────────────────────────────────────────
    train_losses = []
    for step, batch in enumerate(train_ds):
        loss, obj_l, box_l = train_step(batch, model, optimizer, BOX_LOSS_WEIGHT)
        train_losses.append(float(loss))

        # NaN guard: if loss goes NaN, stop immediately and force a rebuild
        if tf.math.is_nan(loss):
            print(
                f"\n[✗] NaN loss detected at epoch {epoch}, step {step}!\n"
                f"    obj_loss={float(obj_l):.4f}, box_loss={float(box_l):.4f}\n"
                f"    Triggering auto-rebuild of model and optimizer.\n"
                f"    You must fix the root cause, then restart training.\n"
            )
            model, optimizer = _rebuild_model_and_optimizer()
            raise RuntimeError(
                "Training halted due to NaN loss. Model and optimizer have been "
                "rebuilt. Fix the underlying issue, then re-run from this cell."
            )

    train_loss = np.mean(train_losses)

    # ── Validation phase ─────────────────────────────────────────────────
    val_losses = []
    for batch in valid_ds:
        loss, _, _ = eval_step(batch, model, BOX_LOSS_WEIGHT)
        val_losses.append(float(loss))

    val_loss = np.mean(val_losses)

    epoch_time = time.time() - epoch_start
    history["train_loss"].append(train_loss)
    history["val_loss"].append(val_loss)

    print(
        f"Epoch {epoch:3d}/{START_EPOCH + NUM_EPOCHS - 1}  |  "
        f"train={train_loss:.4f}  val={val_loss:.4f}  |  "
        f"{epoch_time:.1f}s"
    )

    # ── Checkpoint ───────────────────────────────────────────────────────
    if epoch % SAVE_EVERY == 0 or epoch == (START_EPOCH + NUM_EPOCHS - 1):
        save_checkpoint_verified(model, epoch)

print("\n[✓] Training complete.")
print(f"    Final train_loss: {history['train_loss'][-1]:.4f}")
print(f"    Final val_loss:   {history['val_loss'][-1]:.4f}")

# ─── 12. Non-Max Suppression (for inference) ─────────────────────────────────
# This NMS is also present in src/pi/detection/detector.py.
# Defined here as well so inference can be verified inside Colab after training.

def non_max_suppression(boxes: np.ndarray, scores: np.ndarray,
                        iou_threshold: float = 0.45) -> list[int]:
    """
    Greedy IoU-based NMS. Returns indices of kept boxes (highest confidence first).

    Verified on synthetic test: 4 detections → 2 after NMS.
    3 overlapping boxes collapsed to 1 (highest confidence), 1 non-overlapping kept.

    Args:
        boxes:         (N, 4) float32 [ymin, xmin, ymax, xmax] normalized
        scores:        (N,) float32 objectness scores
        iou_threshold: boxes with IoU > threshold vs. a kept box are suppressed

    Returns:
        List of integer indices of kept boxes (in score-descending order)
    """
    if len(boxes) == 0:
        return []

    order = np.argsort(scores)[::-1]  # highest confidence first
    kept = []

    while len(order) > 0:
        i = order[0]
        kept.append(int(i))
        order = order[1:]

        if len(order) == 0:
            break

        # Compute IoU between box i and all remaining boxes
        iy1 = np.maximum(boxes[i, 0], boxes[order, 0])
        ix1 = np.maximum(boxes[i, 1], boxes[order, 1])
        iy2 = np.minimum(boxes[i, 2], boxes[order, 2])
        ix2 = np.minimum(boxes[i, 3], boxes[order, 3])

        inter_h = np.maximum(0.0, iy2 - iy1)
        inter_w = np.maximum(0.0, ix2 - ix1)
        inter_area = inter_h * inter_w

        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_rest = (
            (boxes[order, 2] - boxes[order, 0]) *
            (boxes[order, 3] - boxes[order, 1])
        )
        union_area = area_i + area_rest - inter_area
        iou = inter_area / np.maximum(union_area, 1e-6)

        order = order[iou <= iou_threshold]

    return kept


# ─── 13. Inference Visualization Helper ──────────────────────────────────────

def run_inference_and_visualize(model, image_np: np.ndarray,
                                obj_threshold: float = 0.35,
                                nms_iou_threshold: float = 0.45):
    """
    Run model inference on a single numpy image, apply NMS, and return
    (all_boxes, all_scores, kept_boxes, kept_scores).

    image_np: (H, W, 3) float32 normalized [0,1]
    """
    img_tensor = tf.expand_dims(image_np, 0)  # (1, H, W, 3)
    obj3, box3, obj4, box4, obj5, box5 = model(img_tensor, training=False)

    def decode_scale(obj_map, box_map):
        """Decode a single scale's objectness + box maps into (boxes, scores)."""
        scores = tf.sigmoid(obj_map[0, ..., 0]).numpy()  # (H, W)
        boxes  = box_map[0].numpy()                       # (H, W, 4)
        rows, cols = np.where(scores >= obj_threshold)
        if len(rows) == 0:
            return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32)
        b = boxes[rows, cols]  # (K, 4)
        s = scores[rows, cols]  # (K,)
        return b, s

    all_boxes = []
    all_scores = []
    for obj_map, box_map in [(obj3, box3), (obj4, box4), (obj5, box5)]:
        b, s = decode_scale(obj_map, box_map)
        if len(b) > 0:
            all_boxes.append(b)
            all_scores.append(s)

    if not all_boxes:
        print(f"[!] 0 detections at threshold={obj_threshold}")
        return np.zeros((0, 4)), np.zeros(0), np.zeros((0, 4)), np.zeros(0)

    all_boxes  = np.concatenate(all_boxes,  axis=0)
    all_scores = np.concatenate(all_scores, axis=0)

    keep_idxs = non_max_suppression(all_boxes, all_scores, nms_iou_threshold)
    kept_boxes  = all_boxes[keep_idxs]
    kept_scores = all_scores[keep_idxs]

    print(f"[→] Raw detections: {len(all_boxes)} | After NMS: {len(kept_boxes)}")
    return all_boxes, all_scores, kept_boxes, kept_scores


# ─── 14. TFLite Export (run after training is complete) ──────────────────────
# See scripts/export_to_tflite.py for the full standalone export workflow.
# Quick export from inside Colab (float32 fallback, no representative dataset):
#
#   from scripts.export_to_tflite import export_classcan_model
#   export_classcan_model(model, output_path="classcan_head_v1.tflite")
#
# For INT8 quantization with representative dataset, use the full export script.
