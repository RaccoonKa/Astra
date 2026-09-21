import subprocess
import sys
import shutil

print(">>> Removing old environment...")
shutil.rmtree(".venv_wsl", ignore_errors=True)

commands = [
    (">>> Step 1: Installing Python 3.10 and system packages in Linux...",
     'wsl -u root -e bash -c "apt-get update && apt-get install -y software-properties-common curl espeak-ng build-essential && add-apt-repository -y ppa:deadsnakes/ppa && apt-get update && apt-get install -y python3.10 python3.10-venv python3.10-dev python3.10-distutils"'),

    (">>> Step 2: Creating clean Python 3.10 virtual environment...",
     'wsl -e bash -c "python3.10 -m venv --without-pip .venv_wsl && chmod -R +x .venv_wsl/bin"'),

    (">>> Step 3: Installing fresh pip...",
     'wsl -e bash -c "curl -sS https://bootstrap.pypa.io/get-pip.py | .venv_wsl/bin/python3.10"'),

    (">>> Step 4: Installing PyTorch (CUDA 12.1), pip 24.0, and dependencies...",
     'wsl -e bash -lic "source .venv_wsl/bin/activate && pip install \\"pip==24.0\\" wheel setuptools && pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121 && pip install \\"pytorch-lightning~=1.7.0\\" piper-phonemize tensorboard onnxruntime cython"'),

    (">>> Step 5: Installing local piper_train and compiling monotonic_align...",
     'wsl -e bash -lic "source .venv_wsl/bin/activate && '
     'if [ -d piper/src/python ]; then '
     '  cd piper/src/python && pip install -e . && (sed -i -e \'s/\\r$//\' build_monotonic_align.sh 2>/dev/null || true) && bash build_monotonic_align.sh; '
     'elif [ -f piper/setup.py ]; then '
     '  cd piper && pip install -e .; '
     'else '
     '  echo \'piper directory not found!\'; exit 1; '
     'fi"')
]

for desc, cmd in commands:
    print(f"\n{desc}")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        shell=True
    )

    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()

    process.wait()
    if process.returncode != 0:
        print(f"\n[Error] Command failed with exit code {process.returncode}")
        sys.exit(1)

print("\nEnvironment setup complete! Ready to execute run_voice.py.")