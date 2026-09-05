import os


wavs_dir = os.path.abspath("dataset/wavs")

count = 0
for filename in os.listdir(wavs_dir):
    if filename.endswith(".WAV"):
        old_path = os.path.join(wavs_dir, filename)
        new_path = os.path.join(wavs_dir, filename[:-4] + ".wav")
        os.rename(old_path, new_path)
        count += 1

print(f"Переименовано файлов: {count} ✨")