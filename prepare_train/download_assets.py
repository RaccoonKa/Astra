from pathlib import Path
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset" / "ru_go_emotions"
MODEL_DIR = BASE_DIR / "models" / "rubert-tiny2"

print("Скачивание датасета seara/ru_go_emotions...")
dataset = load_dataset("seara/ru_go_emotions", "simplified")
dataset.save_to_disk(str(DATASET_DIR))
print(f"Датасет успешно сохранен в: {DATASET_DIR}")

print("Скачивание модели и токенизатора...")
model_name = "cointegrated/rubert-tiny2"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(
    model_name,
    num_labels=28,
    problem_type="multi_label_classification"
)

tokenizer.save_pretrained(str(MODEL_DIR))
model.save_pretrained(str(MODEL_DIR))
print(f"Модель и токенизатор сохранены в: {MODEL_DIR}")