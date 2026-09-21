import os
import shutil
import subprocess
import sys

output_dir = "test_results"
os.makedirs(output_dir, exist_ok=True)

model_int8 = "exported/astra_voice_int8.onnx"
model_raw = "exported/astra_voice_raw.onnx"

if os.path.exists(model_int8):
    target_model = model_int8
elif os.path.exists(model_raw):
    target_model = model_raw
else:
    print(f"Error: ONNX model not found in the exported/ folder.")
    print("First, perform the export using export_voice.py.")
    sys.exit(1)

config_source = "training_dir/config.json"
config_target = f"{target_model}.json"

if not os.path.exists(config_target):
    if os.path.exists(config_source):
        shutil.copy(config_source, config_target)
        print(f"The config has been copied: {config_target}")
    else:
        print(f"Error:  not found {config_source}")
        sys.exit(1)

phrases = [
    (
        "01_greeting.wav",
        "Привет, Свят! Голосовой модуль Астры успешно откалиброван и готов к работе."
    ),
    (
        "02_time_and_numbers.wav",
        "Системное время — одиннадцать часов двадцать четыре минуты. Все службы запущены в штатном режиме."
    ),
    (
        "03_question.wav",
        "Какую задачу запланируем на сегодня? Могу проверить почту, открыть проект или включить музыку."
    ),
    (
        "04_security_alert.wav",
        "Внимание! Зафиксирована попытка доступа. Требуется подтверждение слепка голоса владельца."
    ),
    (
        "05_technical_terms.wav",
        "Синхронизация завершена. Скорость инференса нейросети составляет менее десяти миллисекунд."
    )
]

print(f"Launching the generation of test audio via the model: {target_model}\n")

for filename, text in phrases:
    out_wav = os.path.join(output_dir, filename)
    print(f"Generation: {filename}...")
    print(f"Text: «{text}»")

    escaped_text = text.replace('"', '\\"')
    cmd = [
        "wsl", "-e", "bash", "-lic",
        f"source .venv_wsl/bin/activate && "
        f"python3 -c 'import piper' 2>/dev/null || pip install -q piper-tts && "
        f"echo \"{escaped_text}\" | piper --model {target_model} --output_file {out_wav}"
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"Generation error {filename}: {proc.stderr}")
    else:
        print(f"Successfully saved: {out_wav}\n")

print(f"All files have been generated and are available in the folder: {os.path.abspath(output_dir)}")