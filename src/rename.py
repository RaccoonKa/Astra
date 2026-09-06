import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw_dir = os.path.join(base_dir, "data", "raw")

count = 0

if os.path.exists(raw_dir):
    for root, _, files in os.walk(raw_dir):
        for filename in files:
            if filename.endswith(".WAV"):
                old_path = os.path.join(root, filename)
                temp_path = os.path.join(root, filename + ".tmp")
                new_path = os.path.join(root, filename[:-4] + ".wav")

                os.rename(old_path, temp_path)
                os.rename(temp_path, new_path)
                count += 1
                print(f"Переименован: {filename} -> {os.path.basename(new_path)}")

print(f"Всего переименовано: {count} ✨")