import os
import json
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer


class JointNLU:
    def __init__(self, model_dir="optimized_models/joint_nlu"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        full_model_dir = os.path.join(base_dir, model_dir)

        config_path = os.path.join(full_model_dir, "nlu_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            self.id2intent = {int(k): v for k, v in cfg["id2intent"].items()}
            self.id2slot = {int(k): v for k, v in cfg["id2slot"].items()}

        self.tokenizer = AutoTokenizer.from_pretrained(full_model_dir, local_files_only=True)

        onnx_model_path = os.path.join(full_model_dir, "model_quant.onnx")
        self.session = ort.InferenceSession(onnx_model_path, providers=["CPUExecutionProvider"])

    def predict(self, text):
        if not text:
            return None, 0.0, {}

        text_low = text.lower()
        inputs = self.tokenizer(text_low, return_offsets_mapping=True, return_tensors="np")
        offset_mapping = inputs["offset_mapping"][0].tolist()

        ort_inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        }

        intent_logits, slot_logits = self.session.run(None, ort_inputs)

        exp_logits = np.exp(intent_logits[0] - np.max(intent_logits[0]))
        intent_probs = exp_logits / exp_logits.sum()

        predicted_idx = int(np.argmax(intent_probs))
        confidence_val = float(intent_probs[predicted_idx])
        intent_name = self.id2intent.get(predicted_idx, None)

        slot_preds = np.argmax(slot_logits[0], axis=-1)

        slots = {}
        current_entity = None
        current_start = None
        current_end = None

        for pred, (start, end) in zip(slot_preds, offset_mapping):
            if start == end:
                continue

            label = self.id2slot.get(int(pred), "O")

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