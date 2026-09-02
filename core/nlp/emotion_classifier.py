import os
import sys
import numpy as np
import librosa
import onnxruntime as ort
from core.utils.config import get_resource_path

EMOTION_LABELS = ["neutral", "happy", "sad", "angry", "other"]

EMOTION_TRANSLATION = {
    "neutral": "спокойный / нейтральный",
    "happy": "радость / позитив",
    "sad": "грусть / усталость",
    "angry": "раздражение / злость",
    "other": "прочее"
}

class EmotionClassifier:
    def __init__(self, model_rel_path="optimized_models/emotion_crnn/model_crnn_quant.onnx"):
        path_parts = model_rel_path.replace("\\", "/").split("/")
        model_path = get_resource_path(*path_parts)

        if not os.path.exists(model_path):
            print(f"[EMOTION WARNING]: Файл модели не найден: {model_path}")
            self.session = None
            return

        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])

    def _extract_3channel_features(self, audio_np):
        if len(audio_np) < 16000:
            audio_np = np.pad(audio_np, (0, 16000 - len(audio_np)), mode='constant')
        elif len(audio_np) > 80000:
            audio_np = audio_np[:80000]

        mel = librosa.feature.melspectrogram(
            y=audio_np,
            sr=16000,
            n_fft=1024,
            hop_length=256,
            win_length=1024,
            n_mels=128,
            power=2.0
        )
        mel_db = librosa.power_to_db(mel, ref=np.max)

        delta = librosa.feature.delta(mel_db)
        delta2 = librosa.feature.delta(mel_db, order=2)

        mel_norm = (mel_db - np.mean(mel_db)) / (np.std(mel_db) + 1e-6)
        delta_norm = (delta - np.mean(delta)) / (np.std(delta) + 1e-6)
        delta2_norm = (delta2 - np.mean(delta2)) / (np.std(delta2) + 1e-6)

        three_channel = np.stack([mel_norm, delta_norm, delta2_norm], axis=0)
        three_channel = np.expand_dims(three_channel, axis=0)

        return three_channel.astype(np.float32)

    def predict(self, audio_bytes_or_np):
        if self.session is None or audio_bytes_or_np is None:
            return "neutral", 1.0

        try:
            if isinstance(audio_bytes_or_np, (bytes, bytearray)):
                audio_np = np.frombuffer(audio_bytes_or_np, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_np = audio_bytes_or_np

            if len(audio_np) < 8000:
                return "neutral", 1.0

            feats = self._extract_3channel_features(audio_np)
            logits = self.session.run(None, {"mel_spectrogram": feats})[0]

            exp_logits = np.exp(logits[0] - np.max(logits[0]))
            probs = exp_logits / exp_logits.sum()

            pred_idx = int(np.argmax(probs))
            emotion = EMOTION_LABELS[pred_idx]
            confidence = float(probs[pred_idx])

            return emotion, confidence
        except Exception as e:
            print(f"[EMOTION ERROR]: {e}")
            return "neutral", 1.0