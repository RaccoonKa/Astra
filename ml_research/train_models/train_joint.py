# Предупреждение: эта штука ругается на unhashable type из-за глупых проверок библиотек,
# но по какой-то магической причине всё равно обучается до конца. Работает — не трогай!
# Это уже вторая такая штука, но что поделять. Библиотеки кривые :)


import os
import json
import torch
import random
import torch.nn as nn
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from transformers import AutoTokenizer, BertModel, BertPreTrainedModel
from torch.utils.data import DataLoader, Dataset
from torch.nn.utils.rnn import pad_sequence

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "data", "intents_slot_fillings_fixed_2.json")

if not os.path.exists(DATASET_PATH):
    DATASET_PATH = os.path.join(BASE_DIR, "data", "intents_slot_fillings_fixed.json")
if not os.path.exists(DATASET_PATH):
    DATASET_PATH = os.path.join(BASE_DIR, "intents_slot_fillings_fixed.json")

RESULTS_DIR = os.path.join(BASE_DIR, "results", "train_joint")
FINAL_MODEL_DIR = os.path.join(os.path.dirname(BASE_DIR), "models", "joint_nlu")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(FINAL_MODEL_DIR, exist_ok=True)

with open(DATASET_PATH, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

intents_set = sorted(list({item["intent"] for item in raw_data}))
intent2id = {intent: i for i, intent in enumerate(intents_set)}
id2intent = {i: intent for i, intent in enumerate(intents_set)}

entity_types = set()
for item in raw_data:
    for ent in item.get("entities", []):
        entity_types.add(ent["entity"])

slot_list = ["O"]
for ent in sorted(list(entity_types)):
    slot_list.append(f"B-{ent}")
    slot_list.append(f"I-{ent}")

slot2id = {label: i for i, label in enumerate(slot_list)}
id2slot = {i: label for i, label in enumerate(slot_list)}

tokenizer = AutoTokenizer.from_pretrained("cointegrated/rubert-tiny2")

processed_data = []
for item in raw_data:
    text = item["text"].lower()
    intent = item["intent"]
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

    slot_labels = []
    for start, end in offsets:
        if start == end:
            slot_labels.append(-100)
        else:
            slot_labels.append(slot2id.get(char_labels[start], 0))

    processed_data.append({
        "input_ids": tokenized["input_ids"],
        "attention_mask": tokenized["attention_mask"],
        "intent_label": intent2id[intent],
        "slot_labels": slot_labels
    })

random.seed(42)
random.shuffle(processed_data)
split_idx = int(len(processed_data) * 0.85)
train_data = processed_data[:split_idx]
test_data = processed_data[split_idx:]


class JointDataset(Dataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]


def custom_collate_fn(batch):
    input_ids = [torch.tensor(item["input_ids"], dtype=torch.long) for item in batch]
    attention_mask = [torch.tensor(item["attention_mask"], dtype=torch.long) for item in batch]
    intent_labels = torch.tensor([item["intent_label"] for item in batch], dtype=torch.long)
    slot_labels = [torch.tensor(item["slot_labels"], dtype=torch.long) for item in batch]

    input_ids_padded = pad_sequence(input_ids, batch_first=True, padding_value=tokenizer.pad_token_id or 0)
    attention_mask_padded = pad_sequence(attention_mask, batch_first=True, padding_value=0)
    slot_labels_padded = pad_sequence(slot_labels, batch_first=True, padding_value=-100)

    return {
        "input_ids": input_ids_padded,
        "attention_mask": attention_mask_padded,
        "intent_labels": intent_labels,
        "slot_labels": slot_labels_padded
    }


train_loader = DataLoader(JointDataset(train_data), batch_size=16, shuffle=True, collate_fn=custom_collate_fn)
test_loader = DataLoader(JointDataset(test_data), batch_size=16, shuffle=False, collate_fn=custom_collate_fn)


class JointRuBertNLU(BertPreTrainedModel):
    def __init__(self, config, num_intents, num_slots):
        super().__init__(config)
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.intent_classifier = nn.Linear(config.hidden_size, num_intents)
        self.slot_classifier = nn.Linear(config.hidden_size, num_slots)
        self.post_init()

    def forward(self, input_ids, attention_mask=None, intent_labels=None, slot_labels=None):
        outputs = self.bert(input_ids, attention_mask=attention_mask)
        sequence_output = outputs[0]
        pooled_output = outputs[1]

        sequence_output = self.dropout(sequence_output)
        pooled_output = self.dropout(pooled_output)

        intent_logits = self.intent_classifier(pooled_output)
        slot_logits = self.slot_classifier(sequence_output)

        loss = None
        if intent_labels is not None and slot_labels is not None:
            loss_fct_intent = nn.CrossEntropyLoss()
            loss_fct_slot = nn.CrossEntropyLoss(ignore_index=-100)

            intent_loss = loss_fct_intent(intent_logits, intent_labels)
            slot_loss = loss_fct_slot(slot_logits.view(-1, slot_logits.shape[-1]), slot_labels.view(-1))

            loss = intent_loss + slot_loss

        return loss, intent_logits, slot_logits


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Запуск мультизадачного обучения на: {device.type.upper()}")

model = JointRuBertNLU.from_pretrained(
    "cointegrated/rubert-tiny2",
    num_intents=len(intents_set),
    num_slots=len(slot_list)
).to(device)

optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)

epochs = 20
history = {"train_loss": [], "eval_loss": [], "intent_acc": [], "slot_f1": []}
best_score = -1.0
best_metrics = {}

for epoch in range(epochs):
    model.train()
    total_train_loss = 0
    for batch in train_loader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        intent_labels = batch["intent_labels"].to(device)
        slot_labels = batch["slot_labels"].to(device)

        loss, _, _ = model(input_ids, attention_mask=attention_mask, intent_labels=intent_labels,
                           slot_labels=slot_labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_train_loss += loss.item()

    avg_train_loss = total_train_loss / len(train_loader)

    model.eval()
    total_eval_loss = 0
    all_intent_preds = []
    all_intent_labels = []
    all_slot_preds = []
    all_slot_labels = []

    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            intent_labels = batch["intent_labels"].to(device)
            slot_labels = batch["slot_labels"].to(device)

            loss, intent_logits, slot_logits = model(
                input_ids,
                attention_mask=attention_mask,
                intent_labels=intent_labels,
                slot_labels=slot_labels
            )
            total_eval_loss += loss.item()

            i_preds = torch.argmax(intent_logits, dim=-1).cpu().numpy()
            i_lbls = intent_labels.cpu().numpy()
            all_intent_preds.extend(i_preds)
            all_intent_labels.extend(i_lbls)

            s_preds = torch.argmax(slot_logits, dim=-1).cpu().numpy()
            s_lbls = slot_labels.cpu().numpy()

            for p_seq, l_seq in zip(s_preds, s_lbls):
                for p, l in zip(p_seq, l_seq):
                    if l != -100:
                        all_slot_preds.append(id2slot[p])
                        all_slot_labels.append(id2slot[l])

    avg_eval_loss = total_eval_loss / len(test_loader)
    intent_acc = accuracy_score(all_intent_labels, all_intent_preds)
    slot_f1 = f1_score(all_slot_labels, all_slot_preds, average="weighted", zero_division=0)

    combined_score = (intent_acc + slot_f1) / 2.0

    history["train_loss"].append(avg_train_loss)
    history["eval_loss"].append(avg_eval_loss)
    history["intent_acc"].append(intent_acc)
    history["slot_f1"].append(slot_f1)

    print(
        f"Эпоха {epoch + 1:02d}/{epochs} | Loss: {avg_train_loss:.4f} | Eval Loss: {avg_eval_loss:.4f} | Intent Acc: {intent_acc:.4f} | Slot F1: {slot_f1:.4f}")

    if combined_score >= best_score:
        best_score = combined_score
        best_metrics = {
            "intent_accuracy": float(intent_acc),
            "slot_f1": float(slot_f1),
            "eval_loss": float(avg_eval_loss)
        }

        model.save_pretrained(FINAL_MODEL_DIR)
        tokenizer.save_pretrained(FINAL_MODEL_DIR)

nlu_config = {
    "intent2id": intent2id,
    "id2intent": {str(k): v for k, v in id2intent.items()},
    "slot2id": slot2id,
    "id2slot": {str(k): v for k, v in id2slot.items()}
}
with open(os.path.join(FINAL_MODEL_DIR, "nlu_config.json"), "w", encoding="utf-8") as f:
    json.dump(nlu_config, f, ensure_ascii=False, indent=2)

with open(os.path.join(RESULTS_DIR, "metrics_summary.json"), "w", encoding="utf-8") as f:
    json.dump(best_metrics, f, ensure_ascii=False, indent=2)

ep_range = range(1, epochs + 1)

plt.figure(figsize=(8, 5))
plt.plot(ep_range, history["train_loss"], label="Train Loss", color="blue")
plt.plot(ep_range, history["eval_loss"], label="Eval Loss", color="red")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.title("График потерь Joint NLU")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(RESULTS_DIR, "loss_curve.png"))
plt.close()

plt.figure(figsize=(8, 5))
plt.plot(ep_range, history["intent_acc"], label="Intent Accuracy", color="green")
plt.plot(ep_range, history["slot_f1"], label="Slot F1-Score", color="orange")
plt.xlabel("Epoch")
plt.ylabel("Score")
plt.title("Динамика метрик Joint NLU")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(RESULTS_DIR, "metrics_curve.png"))
plt.close()

print(f"\nОбучение завершено! Объединенная модель сохранена в: {FINAL_MODEL_DIR}")