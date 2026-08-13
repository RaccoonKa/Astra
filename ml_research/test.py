import os
import json
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(os.path.dirname(BASE_DIR), "models", "rubert-tiny2_model")

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.eval()

with open(os.path.join(MODEL_DIR, "intent_config.json"), "r", encoding="utf-8") as f:
    config = json.load(f)

id2intent = {int(k): v for k, v in config["id2intent"].items()}

while True:
    text = input("\nВведи команду для Астры (или exit): ")
    if text.lower() == "exit":
        break

    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=64)
    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.softmax(outputs.logits, dim=1)
    conf, pred_id = torch.max(probs, dim=1)

    intent = id2intent[pred_id.item()]
    print(f"Распознанный интент: {intent} (Уверенность: {conf.item():.2f})")