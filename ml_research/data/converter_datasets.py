import json
import pandas as pd
from sklearn.model_selection import train_test_split

with open("intents.json", "r", encoding="utf-8") as f:
    raw_data = json.load(f)

texts = []
labels = []
classes = list(raw_data.keys())
class_to_idx = {cls_name: i for i, cls_name in enumerate(classes)}
idx_to_class = {i: cls_name for i, cls_name in enumerate(classes)}

for intent, phrases in raw_data.items():
    label_idx = class_to_idx[intent]
    for phrase in phrases:
        texts.append(phrase)
        labels.append(label_idx)

df = pd.DataFrame({"text": texts, "label": labels})

train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])

train_df.to_csv("train_dataset.csv", index=False)
val_df.to_csv("val_dataset.csv", index=False)

config = {
    "classes": classes,
    "class_to_idx": class_to_idx,
    "idx_to_class": idx_to_class,
    "input_dim": len(classes)
}

with open("intent_config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=4)