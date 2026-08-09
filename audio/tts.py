import torch
import sounddevice as sd
import numpy as np
from scipy.signal import butter, filtfilt
from PyQt6.QtCore import QThread, pyqtSignal


class TTSThread(QThread):
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path="models/v4_ru.pt", parent=None):
        super().__init__(parent)
        self.device = torch.device('cpu')
        self.model = None
        self.model_path = model_path
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

    def start_with_greeting(self, greeting_text="Привет, Светозар"):
        self.initial_greeting = greeting_text
        self.start()

    def run(self):
        try:
            self._init_model()

            text = self.initial_greeting if self.initial_greeting else self.text_to_speak
            self.initial_greeting = ""

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