import os
import glob
import shutil
import subprocess
from onnxruntime.quantization import quantize_dynamic, QuantType

logs_dir = "training_dir_whisper/logs/lightning_logs"
if not os.path.exists(logs_dir):
    raise FileNotFoundError("No whisper training logs found. First, start the training.")

versions = sorted(glob.glob(os.path.join(logs_dir, "version_*")), key=os.path.getmtime)
latest_version = versions[-1]
checkpoints = glob.glob(os.path.join(latest_version, "checkpoints", "*.ckpt"))
best_ckpt = checkpoints[-1]

print(f"Checkpoint found: {best_ckpt}")

os.makedirs("exported", exist_ok=True)
onnx_raw = "exported/astra_whisper_raw.onnx"
onnx_quant = "exported/astra_whisper_int8.onnx"

cmd = [
    "wsl", "-e", "bash", "-lic",
    f"source .venv_wsl/bin/activate && python3 -m piper_train.export_onnx {best_ckpt} {onnx_raw}"
]

print(">>> Exporting PyTorch whisper model to ONNX...")
subprocess.run(cmd, check=True)

print(">>> Launching dynamic quantization (INT8)...")
quantize_dynamic(
    model_input=onnx_raw,
    model_output=onnx_quant,
    weight_type=QuantType.QInt8
)

config_src = "training_dir_whisper/config.json"
if os.path.exists(config_src):
    shutil.copy(config_src, f"{onnx_quant}.json")
    shutil.copy(config_src, f"{onnx_raw}.json")
    print("Config successfully copied to exported/")

raw_size = os.path.getsize(onnx_raw) / (1024 * 1024)
quant_size = os.path.getsize(onnx_quant) / (1024 * 1024)

print("\nDone!")
print(f"Base ONNX: {raw_size:.2f} MB")
print(f"Quantized ONNX: {quant_size:.2f} MB")