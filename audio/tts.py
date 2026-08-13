import re
import os
import torch
import sounddevice as sd
import numpy as np
from scipy.signal import butter, filtfilt
from PyQt6.QtCore import QThread, pyqtSignal


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL_PATH = os.path.join(BASE_DIR, "models", "v4_ru.pt")


class TTSThread(QThread):
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path=None, parent=None):
        super().__init__(parent)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.model_path = model_path if model_path else DEFAULT_MODEL_PATH
        self.text_to_speak = ""
        self.speaker = 'kseniya'
        self.sample_rate = 48000
        self.initial_greeting = ""

    def _init_model(self):
        if self.model is None:
            torch.set_num_threads(4)
            importer = torch.package.PackageImporter(self.model_path)
            self.model = importer.load_pickle("tts_models", "model")
            self.model.to(self.device)

            with torch.inference_mode():
                try:
                    self.model.apply_tts(
                        text="Тестовая нормализация текста, цифр 123 и расстановка всех ударений.",
                        speaker=self.speaker,
                        sample_rate=self.sample_rate
                    )
                except Exception:
                    pass

    def _soften_audio(self, audio_np, cutoff=7000):
        nyquist = 0.5 * self.sample_rate
        normal_cutoff = cutoff / nyquist
        b, a = butter(1, normal_cutoff, btype='low', analog=False)
        return filtfilt(b, a, audio_np)

    def _clean_text_for_tts(self, text):
        if not text:
            return ""

        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U000025B6"
            "\U0001F900-\U0001F9FF"
            "\U0001FA70-\U0001FAFF"
            "\u2600-\u26FF"
            "\u2700-\u27BF"
            "]+", flags=re.UNICODE
        )
        cleaned = emoji_pattern.sub("", text)
        cleaned = re.sub(r'[:;=]-?[()DOPpP|/\\]|<3', '', cleaned)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def start_with_greeting(self, greeting_text="Привет!"):
        self.initial_greeting = greeting_text
        self.start()

    def run(self):
        try:
            self._init_model()

            raw_text = self.initial_greeting if self.initial_greeting else self.text_to_speak
            self.initial_greeting = ""

            text = self._clean_text_for_tts(raw_text)

            if not text:
                return

            with torch.inference_mode():
                audio = self.model.apply_tts(
                    text=text,
                    speaker=self.speaker,
                    sample_rate=self.sample_rate
                )

            audio_np = audio.numpy()
            audio_np = self._soften_audio(audio_np, cutoff=7000)

            padding = np.zeros(int(self.sample_rate * 0.4), dtype=np.float32)
            audio_padded = np.concatenate([audio_np, padding])

            self.speaking_started.emit()
            sd.play(audio_padded, self.sample_rate)
            sd.wait()
        except Exception as e:
            print(f"[TTS Error]: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.speaking_finished.emit()

    def say(self, text, speaker='kseniya'):
        if self.isRunning():
            sd.stop()
            self.wait()
        self.text_to_speak = text
        self.speaker = speaker
        self.start()