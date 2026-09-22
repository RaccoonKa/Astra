import json
import numpy as np
import torch
from datasets import Dataset, load_from_disk
from sklearn.metrics import f1_score
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments
)

from config import (
    DATASET_DIR,
    CUSTOM_DATASET_PATH,
    MODEL_INPUT_DIR,
    OUTPUT_DIR,
    FINAL_MODEL_DIR,
    EMOTIONS,
    EMOTION2ID,
    ID2EMOTION,
    RAW_GO_EMOTIONS,
    RAW_TO_MACRO
)

tokenizer = AutoTokenizer.from_pretrained(str(MODEL_INPUT_DIR))

def convert_labels(raw_labels):
    macro_set = set()
    for lbl in raw_labels:
        if isinstance(lbl, int) and lbl < len(RAW_GO_EMOTIONS):
            raw_name = RAW_GO_EMOTIONS[lbl]
            macro_name = RAW_TO_MACRO.get(raw_name)
            if macro_name:
                macro_set.add(macro_name)
        elif isinstance(lbl, str):
            if lbl in EMOTION2ID:
                macro_set.add(lbl)
            elif lbl in RAW_TO_MACRO:
                macro_set.add(RAW_TO_MACRO[lbl])
            elif lbl in ("sarcasm_annoyance", "anger"):
                macro_set.add("negative_sarcasm")

    if not macro_set:
        macro_set.add("neutral")

    return [EMOTION2ID[m] for m in macro_set]

def load_clean_datasets(oversample_factor=10):
    base_data = load_from_disk(str(DATASET_DIR))
    train_raw = base_data["train"]
    val_raw = base_data["validation"]

    train_texts = [
        str(r).strip() if (r is not None and str(r).strip()) else str(t or "")
        for r, t in zip(train_raw["ru_text"], train_raw["text"])
    ]
    train_labels = [convert_labels(lbls) for lbls in train_raw["labels"]]

    if CUSTOM_DATASET_PATH.exists():
        with open(CUSTOM_DATASET_PATH, "r", encoding="utf-8") as f:
            custom_items = json.load(f)

        custom_texts = []
        custom_labels = []
        for item in custom_items:
            t = item.get("text", "").strip()
            if not t:
                continue
            emolist = item.get("emotions", [])
            ids = convert_labels(emolist)
            custom_texts.append(t)
            custom_labels.append(ids)

        if custom_texts:
            print(f"Пользовательских уникальных фраз: {len(custom_texts)}")
            print(f"Применяем оверсэмплинг x{oversample_factor}...")
            for _ in range(oversample_factor):
                train_texts.extend(custom_texts)
                train_labels.extend(custom_labels)
            print(f"Итого пользовательских реплик в трейне: {len(custom_texts) * oversample_factor}")

    train_ds = Dataset.from_dict({
        "text": train_texts,
        "label_ids": train_labels
    }).shuffle(seed=42)

    val_texts = [
        str(r).strip() if (r is not None and str(r).strip()) else str(t or "")
        for r, t in zip(val_raw["ru_text"], val_raw["text"])
    ]
    val_labels = [convert_labels(lbls) for lbls in val_raw["labels"]]

    val_ds = Dataset.from_dict({
        "text": val_texts,
        "label_ids": val_labels
    })

    return train_ds, val_ds

def preprocess_function(examples):
    encoded = tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=64
    )

    batch_ids = examples["label_ids"]
    labels_matrix = np.zeros((len(batch_ids), len(EMOTIONS)), dtype=np.float32)

    for i, ids in enumerate(batch_ids):
        for label_id in ids:
            if isinstance(label_id, int) and label_id < len(EMOTIONS):
                labels_matrix[i, label_id] = 1.0

    encoded["labels"] = labels_matrix
    return encoded

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    probs = 1.0 / (1.0 + np.exp(-logits))
    preds = (probs > 0.35).astype(int)
    f1_micro = f1_score(labels, preds, average="micro", zero_division=0)
    f1_macro = f1_score(labels, preds, average="macro", zero_division=0)
    return {"f1_micro": f1_micro, "f1_macro": f1_macro}

def run_training():
    train_data, val_data = load_clean_datasets(oversample_factor=10)

    print("Токенизация датасетов под 5 категорий...")
    train_tokenized = train_data.map(
        preprocess_function,
        batched=True,
        remove_columns=["text", "label_ids"]
    )
    val_tokenized = val_data.map(
        preprocess_function,
        batched=True,
        remove_columns=["text", "label_ids"]
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        str(MODEL_INPUT_DIR),
        num_labels=len(EMOTIONS),
        id2label=ID2EMOTION,
        label2id=EMOTION2ID,
        problem_type="multi_label_classification",
        ignore_mismatched_sizes=True
    )

    device_use_fp16 = torch.cuda.is_available()

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR / "checkpoints"),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=5e-5,
        per_device_train_batch_size=64,
        per_device_eval_batch_size=64,
        num_train_epochs=3,
        weight_decay=0.01,
        fp16=device_use_fp16,
        logging_steps=100,
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        report_to="none"
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=val_tokenized,
        compute_metrics=compute_metrics
    )

    print("Запуск обучения...")
    trainer.train()

    print(f"Сохранение модели в {FINAL_MODEL_DIR}...")
    FINAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(FINAL_MODEL_DIR))
    tokenizer.save_pretrained(str(FINAL_MODEL_DIR))
    print("Готово!")

if __name__ == "__main__":
    run_training()