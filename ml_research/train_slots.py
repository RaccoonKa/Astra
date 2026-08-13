# Предупреждение: эта штука ругается на unhashable type из-за глупых проверок библиотек,
# но по какой-то магической причине всё равно обучается до конца. Работает — не трогай!


import os
import json
import torch
import random
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
from transformers import AutoTokenizer, AutoModelForTokenClassification
from torch.utils.data import DataLoader, Dataset
from torch.nn.utils.rnn import pad_sequence

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "data", "intents_slot_fillings_fixed_2.json")

if not os.path.exists(DATASET_PATH):
    DATASET_PATH = os.path.join(BASE_DIR, "data", "intents_slot_fillings_fixed.json")
if not os.path.exists(DATASET_PATH):
    DATASET_PATH = os.path.join(BASE_DIR, "intents_slot_fillings_fixed.json")

RESULTS_DIR = os.path.join(BASE_DIR, "results", "train_slots")
FINAL_MODEL_DIR = os.path.join(os.path.dirname(BASE_DIR), "models", "slot_filler")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(FINAL_MODEL_DIR, exist_ok=True)

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

entity_types = set()
for item in raw_data:
    for ent in item.get("entities", []):
        entity_types.add(ent["entity"])

label_list = ["O"]
for ent in sorted(list(entity_types)):
    label_list.append(f"B-{ent}")
    label_list.append(f"I-{ent}")

label2id = {label: i for i, label in enumerate(label_list)}
id2label = {i: label for i, label in enumerate(label_list)}

tokenizer = AutoTokenizer.from_pretrained("cointegrated/rubert-tiny2")

processed_data = []
for item in raw_data:
    text = item["text"].lower()
    entities = item.get("entities", [])
    char_labels = ["O"] * len(text)

    for ent in entities:
        start = ent["start"]
        end = ent["end"]
        ent_type = ent["entity"]
        if start < len(text) and end <= len(text):
            char_labels[start] = f"B-{ent_type}"
            for i in range(start + 1, end):
                char_labels[i] = f"I-{ent_type}"

    tokenized = tokenizer(text, return_offsets_mapping=True, truncation=True, max_length=64)
    offsets = tokenized["offset_mapping"]
    labels = []

    for start, end in offsets:
        if start == end:
            labels.append(-100)
        else:
            labels.append(label2id.get(char_labels[start], 0))

    processed_data.append({
        "input_ids": tokenized["input_ids"],
        "attention_mask": tokenized["attention_mask"],
        "labels": labels
    })

random.seed(42)
random.shuffle(processed_data)
split_idx = int(len(processed_data) * 0.85)
train_data = processed_data[:split_idx]
test_data = processed_data[split_idx:]


class SlotDataset(Dataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]


def custom_collate_fn(batch):
    input_ids = [torch.tensor(item["input_ids"], dtype=torch.long) for item in batch]
    attention_mask = [torch.tensor(item["attention_mask"], dtype=torch.long) for item in batch]
    labels = [torch.tensor(item["labels"], dtype=torch.long) for item in batch]

    input_ids_padded = pad_sequence(input_ids, batch_first=True, padding_value=tokenizer.pad_token_id or 0)
    attention_mask_padded = pad_sequence(attention_mask, batch_first=True, padding_value=0)
    labels_padded = pad_sequence(labels, batch_first=True, padding_value=-100)

    return {
        "input_ids": input_ids_padded,
        "attention_mask": attention_mask_padded,
        "labels": labels_padded
    }


train_loader = DataLoader(SlotDataset(train_data), batch_size=16, shuffle=True, collate_fn=custom_collate_fn)
test_loader = DataLoader(SlotDataset(test_data), batch_size=16, shuffle=False, collate_fn=custom_collate_fn)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Запуск обучения на: {device.type.upper()}")

model = AutoModelForTokenClassification.from_pretrained(
    "cointegrated/rubert-tiny2",
    num_labels=len(label_list),
    id2label=id2label,
    label2id=label2id
).to(device)

optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)

epochs = 20
history = {"train_loss": [], "eval_loss": [], "acc": [], "f1": []}
best_f1 = -1.0
best_metrics = {}
best_cm_data = None

for epoch in range(epochs):
    model.train()
    total_train_loss = 0
    for batch in train_loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        outputs = model(**batch)
        loss = outputs.loss

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_train_loss += loss.item()

    avg_train_loss = total_train_loss / len(train_loader)

    model.eval()
    total_eval_loss = 0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in test_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            total_eval_loss += outputs.loss.item()

            preds = torch.argmax(outputs.logits, dim=-1).cpu().numpy()
            lbls = batch["labels"].cpu().numpy()

            for p_seq, l_seq in zip(preds, lbls):
                for p, l in zip(p_seq, l_seq):
                    if l != -100:
                        all_preds.append(id2label[p])
                        all_labels.append(id2label[l])

    avg_eval_loss = total_eval_loss / len(test_loader)
    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="weighted", zero_division=0)
    precision = precision_score(all_labels, all_preds, average="weighted", zero_division=0)
    recall = recall_score(all_labels, all_preds, average="weighted", zero_division=0)

    history["train_loss"].append(avg_train_loss)
    history["eval_loss"].append(avg_eval_loss)
    history["acc"].append(acc)
    history["f1"].append(f1)

    print(
        f"Эпоха {epoch + 1:02d}/{epochs} | Train Loss: {avg_train_loss:.4f} | Eval Loss: {avg_eval_loss:.4f} | F1: {f1:.4f}")

    if f1 >= best_f1:
        best_f1 = f1
        best_metrics = {
            "accuracy": float(acc),
            "f1": float(f1),
            "precision": float(precision),
            "recall": float(recall),
            "eval_loss": float(avg_eval_loss)
        }
        best_cm_data = (all_labels, all_preds)

        model.save_pretrained(FINAL_MODEL_DIR)
        tokenizer.save_pretrained(FINAL_MODEL_DIR)

slot_config = {
    "label2id": label2id,
    "id2label": {str(k): v for k, v in id2label.items()}
}
with open(os.path.join(FINAL_MODEL_DIR, "slot_config.json"), "w", encoding="utf-8") as f:
    json.dump(slot_config, f, ensure_ascii=False, indent=2)

with open(os.path.join(RESULTS_DIR, "metrics_summary.json"), "w", encoding="utf-8") as f:
    json.dump(best_metrics, f, ensure_ascii=False, indent=2)

ep_range = range(1, epochs + 1)

plt.figure(figsize=(8, 5))
plt.plot(ep_range, history["train_loss"], label="Train Loss", color="blue")
plt.plot(ep_range, history["eval_loss"], label="Eval Loss", color="red")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.title("График потерь (Loss Curve)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(RESULTS_DIR, "loss_curve.png"))
plt.close()

plt.figure(figsize=(8, 5))
plt.plot(ep_range, history["acc"], label="Accuracy", color="green")
plt.plot(ep_range, history["f1"], label="F1-Score", color="orange")
plt.xlabel("Epoch")
plt.ylabel("Score")
plt.title("Динамика метрик (Metrics Curve)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(RESULTS_DIR, "metrics_curve.png"))
plt.close()

if best_cm_data:
    true_lbls, pred_lbls = best_cm_data
    present_labels = sorted(list(set(true_lbls) | set(pred_lbls)))
    cm = confusion_matrix(true_lbls, pred_lbls, labels=present_labels)

    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=present_labels, yticklabels=present_labels)
    plt.xlabel("Предсказанный класс")
    plt.ylabel("Истинный класс")
    plt.title("Матрица ошибок (Confusion Matrix)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "confusion_matrix.png"))
    plt.close()

print(f"\nГотово! Модель сохранена в {FINAL_MODEL_DIR}")
print(f"Отчеты и графики лежат в {RESULTS_DIR}")