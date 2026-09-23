import os
import shutil
import torchaudio

target_dir = os.path.abspath("data/raw/speakers/model_data")
temp_dir = os.path.abspath("data/temp_librispeech")

os.makedirs(target_dir, exist_ok=True)
os.makedirs(temp_dir, exist_ok=True)

dataset = torchaudio.datasets.LIBRISPEECH(root=temp_dir, url="dev-clean", download=True)
libri_speakers_dir = os.path.join(temp_dir, "LibriSpeech", "dev-clean")

imported = 0
for spk_id in sorted(os.listdir(libri_speakers_dir)):
    spk_source_path = os.path.join(libri_speakers_dir, spk_id)
    if not os.path.isdir(spk_source_path):
        continue

    dest_spk_dir = os.path.join(target_dir, f"libri_{spk_id}")
    os.makedirs(dest_spk_dir, exist_ok=True)

    wav_count = 0
    for root, _, files in os.walk(spk_source_path):
        for f in files:
            if f.endswith(".flac"):
                src_file = os.path.join(root, f)
                waveform, sr = torchaudio.load(src_file)
                if sr != 16000:
                    waveform = torchaudio.transforms.Resample(sr, 16000)(waveform)
                    sr = 16000
                out_name = f"{os.path.splitext(f)[0]}.wav"
                torchaudio.save(os.path.join(dest_spk_dir, out_name), waveform, sr)
                wav_count += 1
                if wav_count >= 10:
                    break
        if wav_count >= 10:
            break

    imported += 1

shutil.rmtree(temp_dir)
print(f"Готово! Добавлено {imported} дикторов из LibriSpeech.")