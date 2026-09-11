# ============================================================
# PI BENCHMARK SCRIPT 
# ============================================================
 
import time
import numpy as np
from PIL import Image
from ai_edge_litert import interpreter as tflite
 
IMG_SIZE = 416
 
def benchmark_model(tflite_path, n_runs=20, quantized=False):
    try:
        interpreter = tflite.Interpreter(model_path=tflite_path)
        interpreter.allocate_tensors()
    except RuntimeError as e:
        print(f"  XNNPack failed to prepare ({e}); retrying with num_threads=1 (disables XNNPack)")
        interpreter = tflite.Interpreter(model_path=tflite_path, num_threads=1)
        interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
 
    # dummy input — replace with a real captured frame once camera exposure is fixed
    if quantized:
        dummy_input = np.random.randint(0, 255, (1, IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)
    else:
        dummy_input = np.random.rand(1, IMG_SIZE, IMG_SIZE, 3).astype(np.float32)
 
    # warmup run (first inference is often slower due to memory allocation)
    interpreter.set_tensor(input_details[0]['index'], dummy_input)
    interpreter.invoke()
 
    times = []
    for _ in range(n_runs):
        start = time.time()
        interpreter.set_tensor(input_details[0]['index'], dummy_input)
        interpreter.invoke()
        output = interpreter.get_tensor(output_details[0]['index'])
        times.append(time.time() - start)
 
    times = np.array(times)
    predicted_count = output.sum()
 
    print(f"{tflite_path}:")
    print(f"  Mean inference time: {times.mean()*1000:.1f} ms")
    print(f"  Min/Max: {times.min()*1000:.1f} / {times.max()*1000:.1f} ms")
    print(f"  Std dev: {times.std()*1000:.1f} ms")
    print(f"  Model file size: {os.path.getsize(tflite_path) / (1024*1024):.2f} MB")
    print(f"  Sample predicted count (random noise input, meaningless value): {predicted_count:.1f}")
    print()
 
import os
print("=== FLOAT32 MODEL ===")
benchmark_model('classcan_density_float32.tflite', quantized=False)
 
print("=== INT8 QUANTIZED MODEL ===")
benchmark_model('classcan_density_int8.tflite', quantized=True)
 
# also worth checking system resource usage during inference:
# run `free -h` and `vcgencmd measure_temp` on the Pi during/after this
# to check memory headroom and thermal throttling risk