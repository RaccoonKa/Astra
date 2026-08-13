import os
import json
import torch
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
    TrainerCallback
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

DATASET_PATH = os.path.join(BASE_DIR, "data", "intents_slot_fillings_fixed.json")
RESULTS_DIR = os.path.join(BASE_DIR, "results", "rubert-tiny2_model")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "rubert-tiny2_model")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

texts = [item["text"] for item in data]
raw_intents = [item["intent"] for item in data]

unique_intents = sorted(list(set(raw_intents)))
intent2id = {intent: idx for idx, intent in enumerate(unique_intents)}
id2intent = {idx: intent for idx, intent in enumerate(unique_intents)}

labels = [intent2id[intent] for intent in raw_intents]

train_texts, val_texts, train_labels, val_labels = train_test_split(
    texts, labels, test_size=0.2, random_state=42, stratify=labels
)

model_checkpoint = "cointegrated/rubert-tiny2"
tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)

train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=64)
val_encodings = tokenizer(val_texts, truncation=True, padding=True, max_length=64)

class IntentDataset(Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

train_dataset = IntentDataset(train_encodings, train_labels)
val_dataset = IntentDataset(val_encodings, val_labels)

model = AutoModelForSequenceClassification.from_pretrained(
    model_checkpoint,
    num_labels=len(unique_intents),
    id2label=id2intent,
    label2id=intent2id
)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="weighted")
    acc = accuracy_score(labels, preds)
    return {
        "accuracy": acc,
        "f1": f1,
        "precision": precision,
        "recall": recall
    }

class MetricsLoggerCallback(TrainerCallback):
    def __init__(self):
        self.eval_loss = []
        self.eval_accuracy = []
        self.eval_f1 = []
        self.epochs = []

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs is not None and "eval_loss" in logs:
            self.epochs.append(state.epoch)
            self.eval_loss.append(logs["eval_loss"])
            if "eval_accuracy" in logs:
                self.eval_accuracy.append(logs["eval_accuracy"])
            if "eval_f1" in logs:
                self.eval_f1.append(logs["eval_f1"])

metrics_callback = MetricsLoggerCallback()

training_args = TrainingArguments(
    output_dir=os.path.join(RESULTS_DIR, "rubert-tiny2_model", "checkpoints"),
    eval_strategy="epoch",
    save_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=16,
    num_train_epochs=25,
    weight_decay=0.01,
    load_best_model_at_end=True,
    logging_steps=1,
    report_to="none"
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    processing_class=tokenizer,
    compute_metrics=compute_metrics,
    callbacks=[metrics_callback]
)

trainer.train()

model.save_pretrained(MODEL_DIR)
tokenizer.save_pretrained(MODEL_DIR)

config_data = {
    "intent2id": intent2id,
    "id2intent": id2intent,
    "classes": unique_intents
}
with open(os.path.join(MODEL_DIR, "intent_config.json"), "w", encoding="utf-8") as f:
    json.dump(config_data, f, ensure_ascii=False, indent=4)

epochs = metrics_callback.epochs
eval_loss = metrics_callback.eval_loss
eval_acc = metrics_callback.eval_accuracy
eval_f1 = metrics_callback.eval_f1

if epochs:
    plt.figure(figsize=(10, 6))
    plt.plot(epochs, eval_loss, label="Validation Loss", color="red", marker="o")
    plt.title("Динамика потерь (Validation Loss)")
    plt.xlabel("Эпоха")
    plt.ylabel("Loss")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "rubert-tiny2_model", "loss_curve.png"), dpi=300)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.plot(epochs, eval_acc, label="Accuracy", color="blue", marker="s")
    plt.plot(epochs, eval_f1, label="F1-Score", color="green", marker="^")
    plt.title("Качество модели (Accuracy & F1-Score)")
    plt.xlabel("Эпоха")
    plt.ylabel("Метрика")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "rubert-tiny2_model", "metrics_curve.png"), dpi=300)
    plt.close()

predictions = trainer.predict(val_dataset)
preds = np.argmax(predictions.predictions, axis=1)
cm = confusion_matrix(val_labels, preds)

plt.figure(figsize=(12, 10))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
            xticklabels=unique_intents,
            yticklabels=unique_intents)
plt.title("Матрица ошибок (Confusion Matrix)")
plt.xlabel("Предсказанный класс")
plt.ylabel("Истинный класс")
plt.xticks(rotation=45, ha="right")
plt.yticks(rotation=0)
plt.tight_layout()
plt.savefig(os.path.join(RESULTS_DIR, "rubert-tiny2_model", "confusion_matrix.png"), dpi=300)
plt.close()

summary_metrics = {
    "final_eval_loss": eval_loss[-1] if eval_loss else None,
    "final_accuracy": eval_acc[-1] if eval_acc else None,
    "final_f1": eval_f1[-1] if eval_f1 else None
}
with open(os.path.join(RESULTS_DIR, "rubert-tiny2_model", "metrics_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary_metrics, f, ensure_ascii=False, indent=4)