# Скрипт подготовки сберовского датасета к обучению.
# python ml_research/prepare_dusha.py --setup crowd_small.jsonl команда запуска

import os
import json
import argparse
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SETUPS_DIR = os.path.join(DATA_DIR, "setups")
OUTPUT_CSV = os.path.join(DATA_DIR, "dusha_train.csv")

EMOTION_MAPPING = {
    "positive": "happy",
    "happy": "happy",
    "neutral": "neutral",
    "sad": "sad",
    "angry": "angry",
    "other": "other"
}

def build_wav_index(data_dir):
    print("Сканируем директорию data на наличие .wav файлов...")
    wav_index = {}
    total_files = 0

    for root, _, files in os.walk(data_dir):
        if "setups" in root:
            continue
        for f in files:
            if f.lower().endswith(".wav"):
                full_path = os.path.join(root, f)
                filename = f.lower()
                wav_index[filename] = full_path
                total_files += 1

    print(f"Найдено на диске .wav файлов: {total_files}")
    return wav_index


def parse_jsonl(setup_file, wav_index):
    setup_path = os.path.join(SETUPS_DIR, setup_file)
    if not os.path.exists(setup_path):
        setup_path = os.path.join(DATA_DIR, setup_file)

    if not os.path.exists(setup_path):
        print(f"Файл разметки {setup_file} не найден.")
        return []

    print(f"Читаем разметку: {setup_path}...")
    records = []
    missing_files = 0
    first_row_debug = True

    with open(setup_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)

            if first_row_debug:
                print(f"ℹПример строки из разметки: {data}")
                first_row_debug = False

            audio_raw = (
                data.get("audio_path") or
                data.get("path") or
                data.get("wav") or
                data.get("file_name") or
                data.get("id")
            )
            emotion_raw = data.get("emotion") or data.get("label") or data.get("emo")

            if not audio_raw or not emotion_raw:
                continue

            emotion = EMOTION_MAPPING.get(str(emotion_raw).lower().strip(), "other")

            clean_name = os.path.basename(str(audio_raw)).lower()
            if not clean_name.endswith(".wav"):
                clean_name += ".wav"

            if clean_name in wav_index:
                records.append({
                    "path": wav_index[clean_name],
                    "emotion": emotion
                })
            else:
                missing_files += 1

    if missing_files > 0:
        print(f"Пропущено (не сопоставлено с аудио на диске): {missing_files} строк")

    return records


def main():
    parser = argparse.ArgumentParser(description="Подготовка dusha_train.csv из JSONL разметки")
    parser.add_argument(
        "--setup",
        type=str,
        default="crowd_small.jsonl",
        help="Имя файла разметки из setups/"
    )
    args = parser.parse_args()

    wav_index = build_wav_index(DATA_DIR)
    if not wav_index:
        print("В папке data не найдено ни одного .wav файла. Убедись, что архивы распакованы.")
        return

    records = parse_jsonl(args.setup, wav_index)

    if records:
        df = pd.DataFrame(records)
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
        print(f"\nУспешно собрано {len(df)} аудиозаписей в {OUTPUT_CSV}")
        print("\nРаспределение классов:")
        print(df["emotion"].value_counts())
    else:
        print("Не удалось собрать данные. Проверь имя setup файла.")


if __name__ == "__main__":
    main()