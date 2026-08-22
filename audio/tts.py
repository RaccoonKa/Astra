import re
import os
import sys
import torch
import sounddevice as sd
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from core.utils.config import get_resource_path, load_config

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MODEL_PATH = get_resource_path("optimized_models", "silero_tts", "v4_ru.pt")


class TTSThread(QThread):
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    warmup_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path=None, parent=None):
        super().__init__(parent)
        self.device = torch.device('cpu')
        self.model = None
        self.model_path = model_path if model_path else DEFAULT_MODEL_PATH
        self.text_to_speak = ""
        self.speaker = 'kseniya'
        self.sample_rate = 48000
        self._stopped = False
        self._is_warmup = False
        self._play_cached_flag = False
        self.greeting_to_precache = ""
        self.cached_greeting_audio = None
        self.warmup_text = "Астра"

    def _init_model(self):
        if self.model is None and os.path.exists(self.model_path):
            try:
                torch.set_num_threads(4)
                importer = torch.package.PackageImporter(self.model_path)
                self.model = importer.load_pickle("tts_models", "model")
                self.model.to(self.device)
            except Exception as e:
                print(f"[TTS Init Error]: {e}")

    def _process_audio_level(self, audio_np):
        peak = np.max(np.abs(audio_np))
        if peak > 0.001:
            audio_np = audio_np / peak

        cfg = load_config()
        vol_percent = cfg.get("voice_volume", 100)
        vol_factor = max(0.0, min(1.0, vol_percent / 100.0))

        return (audio_np * vol_factor).astype(np.float32)

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

    def stop(self):
        self._stopped = True
        try:
            sd.stop()
        except Exception:
            pass
        if self.isRunning():
            self.wait(200)

    def start_warmup(self, greeting_text=None, phrase=None):
        self.stop()
        self._is_warmup = True
        self._play_cached_flag = False
        if phrase:
            self.warmup_text = phrase
        if greeting_text:
            self.greeting_to_precache = greeting_text
        self.start()

    def play_cached_greeting(self):
        if self.cached_greeting_audio is not None:
            self.stop()
            self._stopped = False
            self._is_warmup = False
            self._play_cached_flag = True
            self.start()
        else:
            self.say(self.greeting_to_precache if self.greeting_to_precache else "Привет!")

    def say(self, text, speaker='kseniya'):
        self.stop()
        self._is_warmup = False
        self._play_cached_flag = False
        self.text_to_speak = text
        self.speaker = speaker
        self.start()

    def run(self):
        self._stopped = False
        try:
            if not self.model:
                self._init_model()

            if self._is_warmup:
                cleaned_warmup = self._clean_text_for_tts(self.warmup_text)
                if self.model and cleaned_warmup and not self._stopped:
                    with torch.inference_mode():
                        _ = self.model.apply_tts(
                            text=cleaned_warmup,
                            speaker=self.speaker,
                            sample_rate=self.sample_rate
                        )

                if self.greeting_to_precache and not self._stopped:
                    cleaned_greeting = self._clean_text_for_tts(self.greeting_to_precache)
                    with torch.inference_mode():
                        audio = self.model.apply_tts(
                            text=cleaned_greeting,
                            speaker=self.speaker,
                            sample_rate=self.sample_rate
                        )
                    audio_np = self._process_audio_level(audio.numpy())
                    padding = np.zeros(int(self.sample_rate * 0.2), dtype=np.float32)
                    self.cached_greeting_audio = np.concatenate([audio_np, padding])

                self.warmup_finished.emit()
                return

            if self._play_cached_flag:
                self._play_cached_flag = False
                if self.cached_greeting_audio is not None and not self._stopped:
                    self.speaking_started.emit()
                    sd.play(self.cached_greeting_audio, self.sample_rate)
                    while sd.get_stream() and sd.get_stream().active:
                        if self._stopped:
                            sd.stop()
                            break
                        sd.sleep(40)
                return

            text = self._clean_text_for_tts(self.text_to_speak)
            if not text or self._stopped:
                return

            with torch.inference_mode():
                audio = self.model.apply_tts(
                    text=text,
                    speaker=self.speaker,
                    sample_rate=self.sample_rate
                )

            if self._stopped:
                return

            audio_np = self._process_audio_level(audio.numpy())
            padding = np.zeros(int(self.sample_rate * 0.2), dtype=np.float32)
            audio_padded = np.concatenate([audio_np, padding])

            self.speaking_started.emit()
            sd.play(audio_padded, self.sample_rate)

            while sd.get_stream() and sd.get_stream().active:
                if self._stopped:
                    sd.stop()
                    break
                sd.sleep(40)

        except Exception as e:
            print(f"[TTS Error]: {e}")
            self.error_occurred.emit(str(e))
            if self._is_warmup:
                self.warmup_finished.emit()
        finally:
            if not self._is_warmup:
                self.speaking_finished.emit()