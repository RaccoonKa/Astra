import os
from onnxruntime.quantization import quantize_dynamic, QuantType

corrector_dir = "optimized_models/corrector"
onnx_files = ["encoder_model.onnx", "decoder_model.onnx", "decoder_with_past_model.onnx"]

for fname in onnx_files:
    fpath = os.path.join(corrector_dir, fname)
    if os.path.exists(fpath):
        temp_path = os.path.join(corrector_dir, f"temp_{fname}")
        os.replace(fpath, temp_path)
        quantize_dynamic(temp_path, fpath, weight_type=QuantType.QInt8)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"Квантован: {fname}")