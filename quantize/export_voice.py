import os
import glob
import shutil
import subprocess
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
os.chdir(project_root)

logs_dir = Path("training_dir/voice_logs/lightning_logs")
if not logs_dir.exists():
    raise FileNotFoundError("No training logs found. First, start the training.")

versions = sorted(glob.glob(str(logs_dir / "version_*")), key=os.path.getmtime)
latest_version = versions[-1]

checkpoints = sorted(
    glob.glob(str(Path(latest_version) / "checkpoints" / "*.ckpt")),
    key=os.path.getmtime
)

if not checkpoints:
    raise FileNotFoundError("No checkpoints found in the latest version directory.")

best_ckpt = Path(checkpoints[-1]).as_posix()
print(f"Target checkpoint found: {best_ckpt}")

os.makedirs("exported", exist_ok=True)
onnx_raw = "exported/astra_voice_raw.onnx"

cmd = [
    "wsl", "-e", "bash", "-c",
    f"source .venv_wsl/bin/activate && python3 -m piper_train.export_onnx '{best_ckpt}' '{onnx_raw}'"
]

print(">>> Exporting PyTorch model to ONNX via WSL...")
subprocess.run(cmd, check=True)

config_src = "training_dir/config.json"
if os.path.exists(config_src):
    shutil.copy(config_src, f"{onnx_raw}.json")
    print("Config successfully linked to exported raw model.")

raw_size = os.path.getsize(onnx_raw) / (1024 * 1024)

print("\nDone!")
print(f"Exported ONNX model size: {raw_size:.2f} MB")