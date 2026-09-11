import time
import numpy as np
from ai_edge_litert.interpreter import Interpreter

interpreter = Interpreter(model_path="speed_test_v3large_416.tflite")
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()

dummy_input = np.random.rand(1, 416, 416, 3).astype(np.float32)

interpreter.set_tensor(input_details[0]['index'], dummy_input)
interpreter.invoke()

start = time.time()
for _ in range(5):
    interpreter.set_tensor(input_details[0]['index'], dummy_input)
    interpreter.invoke()
print(f"Avg inference time (Pi 3B CPU): {(time.time()-start)/5:.3f}s")
