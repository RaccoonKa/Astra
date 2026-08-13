import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import json
import torch
import torch.nn as nn
from transformers import AutoTokenizer, BertModel, BertPreTrainedModel


class JointRuBertNLU(BertPreTrainedModel):
    def __init__(self, config, num_intents=1, num_slots=1):
        super().__init__(config)
        self.bert = BertModel(config)
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.intent_classifier = nn.Linear(config.hidden_size, num_intents)
        self.slot_classifier = nn.Linear(config.hidden_size, num_slots)
        self.post_init()

    def forward(self, input_ids, attention_mask=None):
        outputs = self.bert(input_ids, attention_mask=attention_mask)
        sequence_output = outputs[0]
        pooled_output = outputs[1]

        sequence_output = self.dropout(sequence_output)
        pooled_output = self.dropout(pooled_output)

        intent_logits = self.intent_classifier(pooled_output)
        slot_logits = self.slot_classifier(sequence_output)

        return intent_logits, slot_logits


class JointNLU:
    def __init__(self, model_dir="models/joint_nlu"):
        self.device = torch.device("cpu")
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        full_model_dir = os.path.join(base_dir, model_dir)

        config_path = os.path.join(full_model_dir, "nlu_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            self.id2intent = {int(k): v for k, v in cfg["id2intent"].items()}
            self.id2slot = {int(k): v for k, v in cfg["id2slot"].items()}

        self.tokenizer = AutoTokenizer.from_pretrained(full_model_dir, local_files_only=True)
        self.model = JointRuBertNLU.from_pretrained(
            full_model_dir,
            num_intents=len(self.id2intent),
            num_slots=len(self.id2slot),
            local_files_only=True
        ).to(self.device)
        self.model.eval()

    def predict(self, text):
        if not text:
            return None, 0.0, {}

        text_low = text.lower()
        inputs = self.tokenizer(text_low, return_offsets_mapping=True, return_tensors="pt")
        offset_mapping = inputs["offset_mapping"][0].tolist()

        with torch.no_grad():
            intent_logits, slot_logits = self.model(
                input_ids=inputs["input_ids"].to(self.device),
                attention_mask=inputs["attention_mask"].to(self.device)
            )

            intent_probs = torch.softmax(intent_logits, dim=-1)
            confidence, predicted_idx = torch.max(intent_probs, dim=-1)
            intent_name = self.id2intent.get(predicted_idx.item(), None)
            confidence_val = confidence.item()

            slot_preds = torch.argmax(slot_logits, dim=-1)[0].cpu().numpy()

        slots = {}
        current_entity = None
        current_start = None
        current_end = None

        for pred, (start, end) in zip(slot_preds, offset_mapping):
            if start == end:
                continue

            label = self.id2slot.get(pred, "O")

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

        return intent_name, confidence_val, slots