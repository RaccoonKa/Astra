import subprocess
import sys

cmd = [
    "wsl",
    "-e", "bash", "-lic",
    "source .venv_wsl/bin/activate && "
    "python3 -m piper_train.preprocess --language ru --input-dir dataset/astra_voice --output-dir training_dir --dataset-format ljspeech --sample-rate 22050 && "
    "python3 train/train_voice.py"
]

print(">>> Pipeline initialization in WSL...")
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
    print("\n>>> Training complete!")
else:
    print(f"\n>>> Error. Code: {process.returncode}")
