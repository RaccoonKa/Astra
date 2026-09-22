from pathlib import Path
from datasets import load_from_disk
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset" / "ru_go_emotions"
OUTPUT_CSV = BASE_DIR / "dataset" / "preview.csv"

dataset = load_from_disk(str(DATASET_DIR))
train_df = pd.DataFrame(dataset["train"].select(range(500)))

train_df[["ru_text", "labels"]].to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
print(f"Превью сохранено в {OUTPUT_CSV}")