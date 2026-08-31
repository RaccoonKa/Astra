import os
import torch
import sounddevice as sd
import numpy as np
from scipy.signal import butter, sosfilt, stft, istft


model_path = os.path.join("optimized_models", "silero_tts", "v4_ru.pt")

print("⏳ Загружаю нейросеть...")
torch.set_num_threads(2)
importer = torch.package.PackageImporter(model_path)
model = importer.load_pickle("tts_models", "model")
model.to(torch.device('cpu'))
print("✅ Астра готова шептаться!\n")


def apply_whisper(audio_np, sample_rate=24000):
    f, t, Zxx = stft(audio_np, fs=sample_rate, nperseg=1024, noverlap=768)

    magnitudes = np.abs(Zxx)
    random_phase = np.exp(1j * np.random.uniform(-np.pi, np.pi, Zxx.shape))
    whisper_Zxx = magnitudes * random_phase

    _, whisper_audio = istft(whisper_Zxx, fs=sample_rate, nperseg=1024, noverlap=768)

    nyq = 0.5 * sample_rate
    hp_sos = butter(4, 300.0 / nyq, btype='high', output='sos')
    whisper_audio = sosfilt(hp_sos, whisper_audio)

    peak = np.max(np.abs(whisper_audio))
    if peak > 0.001:
        whisper_audio = (whisper_audio / peak) * 0.45

    return whisper_audio.astype(np.float32)


while True:
    text = input("Ты: ")
    if text.lower() in ['q', 'й', 'выход']:
        break
    if not text.strip():
        continue

    with torch.inference_mode():
        audio = model.apply_tts(text=text, speaker='kseniya', sample_rate=24000)

    audio_np = audio.numpy()

    whisper_audio = apply_whisper(audio_np, 24000)

    sd.play(whisper_audio, 24000)
    sd.wait()