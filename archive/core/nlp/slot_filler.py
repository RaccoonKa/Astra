# Вторая модель зафайнтюнинная rubert-tiny2, которая была объединена в одну в файле nlu.py
# Файл-архив. В данный момент в проекте НЕ используется!

import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import json
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification


class SlotFiller:
    def __init__(self, model_dir="models/slot_filler"):
        self.device = torch.device("cpu")
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_model_dir = os.path.join(base_dir, model_dir)

        config_path = os.path.join(full_model_dir, "slot_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                self.id2label = {int(k): v for k, v in cfg["id2label"].items()}
        else:
            self.id2label = {}

        self.tokenizer = AutoTokenizer.from_pretrained(full_model_dir, local_files_only=True)
        self.model = AutoModelForTokenClassification.from_pretrained(full_model_dir, local_files_only=True).to(self.device)
        self.model.eval()

    def extract_slots(self, text):
        if not text or not self.id2label:
            return {}

        text_low = text.lower()
        inputs = self.tokenizer(text_low, return_offsets_mapping=True, return_tensors="pt")
        offset_mapping = inputs["offset_mapping"][0].tolist()

        with torch.no_grad():
            outputs = self.model(
                input_ids=inputs["input_ids"].to(self.device),
                attention_mask=inputs["attention_mask"].to(self.device)
            )
            predictions = torch.argmax(outputs.logits, dim=-1)[0].cpu().numpy()

        slots = {}
        current_entity = None
        current_start = None
        current_end = None

        for idx, (pred, (start, end)) in enumerate(zip(predictions, offset_mapping)):
            if start == end:
                continue

            label = self.id2label.get(pred, "O")

            if label.startswith("B-"):
                if current_entity and current_start is not None and current_end is not None:
                    slots[current_entity] = text_low[current_start:current_end].strip()
                current_entity = label[2:]
                current_start = start
                current_end = end
            elif label.startswith("I-") and current_entity == label[2:]:
                current_end = end
            else:
                if current_entity and current_start is not None and current_end is not None:
                    slots[current_entity] = text_low[current_start:current_end].strip()
                    current_entity = None
                    current_start = None
                    current_end = None

        if current_entity and current_start is not None and current_end is not None:
            slots[current_entity] = text_low[current_start:current_end].strip()

        return slots