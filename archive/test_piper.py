import os
import urllib.request
import json
import numpy as np
import sounddevice as sd
import time
import wave
import io

try:
    from piper import PiperVoice
except ImportError:
    print("Библиотека piper-tts не установлена! Напиши в консоли: pip install piper-tts")
    exit()

MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx"
CONFIG_URL = MODEL_URL + ".json"

model_path = "ru_RU-irina-medium.onnx"
config_path = model_path + ".json"


def download_file(url, filename):
    if not os.path.exists(filename):
        print(f"Качаю {filename} (это быстро)...")
        urllib.request.urlretrieve(url, filename)


download_file(MODEL_URL, model_path)
download_file(CONFIG_URL, config_path)

print("⏳ Загружаю Piper...")
voice = PiperVoice.load(model_path, config_path=config_path)

with open(config_path, 'r', encoding='utf-8') as f:
    sample_rate = json.load(f)['audio']['sample_rate']

print(f"✅ Готово! Частота: {sample_rate} Гц")

while True:
    text = input("Ты: ")
    if text.lower() in ['q', 'й', 'выход']:
        break
    if not text.strip():
        continue

    t0 = time.time()

    wav_io = io.BytesIO()

    with wave.open(wav_io, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)

    wav_io.seek(0)
    with wave.open(wav_io, "rb") as wav_read:
        audio_bytes = wav_read.readframes(wav_read.getnframes())

    t1 = time.time()

    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    print(f"⚡ Сгенерировано за {t1 - t0:.3f} сек")
    sd.play(audio_np, sample_rate)
    sd.wait()