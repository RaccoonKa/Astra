import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw_dir = os.path.join(base_dir, "data", "raw")

count = 0

if os.path.exists(raw_dir):
    for root, _, files in os.walk(raw_dir):
        for filename in files:
            name, ext = os.path.splitext(filename)
            if ext.lower() == ".wav" and ext != ".wav":
                old_path = os.path.join(root, filename)
                temp_path = os.path.join(root, f"{name}__temp__.wav")
                new_path = os.path.join(root, f"{name}.wav")

                if os.path.exists(temp_path):
                    os.remove(temp_path)

                os.rename(old_path, temp_path)
                os.rename(temp_path, new_path)
                count += 1
                print(f"{filename} -> {name}.wav")

print(f"Готово! Переименовано файлов: {count}")