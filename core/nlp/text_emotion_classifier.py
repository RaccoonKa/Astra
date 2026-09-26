import os
import numpy as np
import onnxruntime as ort
from transformers import PreTrainedTokenizerFast, AutoTokenizer
from core.utils.config import get_resource_path

EMOTION_CLASSES = [
    ("happy", "радость / похвала"),
    ("angry", "злость / раздражение / сарказм"),
    ("sad", "грусть / усталость"),
    ("surprise", "удивление / восторг"),
    ("neutral", "нейтрально")
]

RU_EMOTIONS = {
    "joy_praise": "радость / похвала",
    "negative_sarcasm": "злость / раздражение / сарказм",
    "sadness_fatigue": "грусть / усталость",
    "surprise": "удивление / восторг",
    "neutral": "нейтрально"
}


class TextEmotionClassifier:
    def __init__(self, model_dir=None):
        if model_dir is None:
            model_dir = get_resource_path("optimized_models", "text_emotions")

        model_dir = os.path.normpath(model_dir)

        tokenizer_json_path = os.path.join(model_dir, "tokenizer.json")
        tokenizer_config_path = os.path.join(model_dir, "tokenizer_config.json")

        if os.path.exists(tokenizer_json_path):
            self.tokenizer = PreTrainedTokenizerFast(
                tokenizer_file=tokenizer_json_path,
                tokenizer_config_file=tokenizer_config_path if os.path.exists(tokenizer_config_path) else None
            )
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)

        if getattr(self.tokenizer, "pad_token", None) is None:
            self.tokenizer.pad_token = "[PAD]"
            self.tokenizer.pad_token_id = 0

        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = 2
        session_options.inter_op_num_threads = 1
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        onnx_path = os.path.join(model_dir, "astra_text_emotions_int8.onnx")
        self.session = ort.InferenceSession(
            onnx_path,
            sess_options=session_options,
            providers=["CPUExecutionProvider"]
        )
        print("[TextEmotion]: Текстовый классификатор эмоций готов к работе! ✨", flush=True)

    def predict(self, text: str):
        if not text or not text.strip():
            return "neutral", "нейтрально", 1.0

        try:
            inputs = self.tokenizer(
                text.strip(),
                return_tensors="np",
                truncation=True,
                max_length=128,
                padding=True
            )

            ort_inputs = {}
            for input_meta in self.session.get_inputs():
                name = input_meta.name
                if name in inputs:
                    ort_inputs[name] = inputs[name].astype(np.int64)

            outputs = self.session.run(None, ort_inputs)
            logits = np.array(outputs[0]).squeeze()

            probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -20.0, 20.0)))

            non_neutral_indices = [0, 1, 2, 3]
            best_idx = max(non_neutral_indices, key=lambda i: probs[i])
            best_conf = float(probs[best_idx])

            if best_conf >= 0.35:
                ui_emo, ru_desc = EMOTION_CLASSES[best_idx]
            else:
                ui_emo, ru_desc = "neutral", "нейтрально"
                best_conf = float(probs[4])

            print(f"[TextEmotion]: '{text}' -> {ui_emo.upper()} ({ru_desc}, conf={best_conf:.2f})", flush=True)
            return ui_emo, ru_desc, best_conf

        except Exception as e:
            print(f"[TextEmotion Predict Error]: {e}", flush=True)
            return "neutral", "нейтрально", 0.0