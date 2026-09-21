import subprocess
import sys

cmd = [
    "wsl",
    "-e", "bash", "-lic",
    "source .venv_wsl/bin/activate && "
    "--input-dir dataset/astra_whisper --output-dir training_dir_whisper --dataset-format ljspeech --sample-rate 22050 && "
    "python3 train/train_whisper.py"
]

print(">>> Initializing Whisper pipeline in WSL...")
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    encoding="utf-8"
)

for line in process.stdout:
    sys.stdout.write(line)
    sys.stdout.flush()

process.wait()
if process.returncode == 0:
    print("\n>>> Whisper training complete!")
else:
    print(f"\n>>> Error. Code: {process.returncode}")