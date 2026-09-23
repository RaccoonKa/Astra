import os
import sys
import re
import numpy as np
import sounddevice as sd
import torch
from PyQt6.QtCore import QThread, pyqtSignal
from piper.voice import PiperVoice
from core.utils.config import get_resource_path, load_config
from core.system.actions import ym_manager

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_SILERO_PATH = get_resource_path("optimized_models", "silero_tts", "v4_ru.pt")
DEFAULT_PIPER_ONNX = get_resource_path("optimized_models", "whisper_tts", "astra_whisper.onnx")
DEFAULT_PIPER_JSON = get_resource_path("optimized_models", "whisper_tts", "astra_whisper.onnx.json")

BRAND_DICTIONARY = {
    "spacex": "Сп+ейс Икс", "tesla": "Т+эсла", "apple": "+Эппл",
    "google": "Г+угл", "samsung": "Самс+унг", "huawei": "Хуав+эй",
    "honor": "+Онор", "xiaomi": "Сяом+и", "x": "+Икс",
    "microsoft": "М+айкрософт", "amazon": "Амаз+он", "meta": "М+ета",
    "facebook": "Ф+ейсбук", "twitter": "Тв+иттер", "instagram": "Инстагр+ам",
    "telegram": "Телегр+ам", "discord": "Д+искорд", "youtube": "Ют+уб",
    "nvidia": "Энв+идиа", "amd": "Эй Эм Д+и", "intel": "+Интел",
    "sony": "С+они", "openai": "+Оупен Эй +Ай", "windows": "В+индоус",
    "linux": "Л+инукс", "steam": "Ст+им", "valve": "В+алв",
    "uber": "+Убер", "spotify": "Спотиф+ай", "netflix": "Н+етфликс",
    "chatgpt": "Чат Джи Пи Т+и", "yandex": "+Яндекс", "vk": "Вэ К+а",
    "bmw": "Бэ Эм В+э", "audi": "+Ауди", "mercedes": "Мерсед+ес"
}


def latin_to_cyrillic(text: str) -> str:
    if not text:
        return ""

    def replace_word(match):
        word = match.group(0)
        low_word = word.lower()
        if low_word in BRAND_DICTIONARY:
            return BRAND_DICTIONARY[low_word]

        w = low_word
        replacements = [
            ("sh", "ш"), ("ch", "ч"), ("th", "т"), ("ph", "ф"),
            ("zh", "ж"), ("kh", "х"), ("ts", "ц"), ("ee", "и"),
            ("oo", "у"), ("ea", "и"), ("ck", "к"), ("qu", "кв"),
            ("ya", "я"), ("yo", "ё"), ("yu", "ю"), ("x", "кс"),
            ("w", "в"), ("j", "дж"), ("c", "к"), ("q", "к")
        ]
        for lat, cyr in replacements:
            w = w.replace(lat, cyr)

        char_map = {
            'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е',
            'z': 'з', 'i': 'и', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н',
            'o': 'о', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у',
            'f': 'ф', 'h': 'х', 'y': 'и'
        }
        return "".join(char_map.get(ch, ch) for ch in w)

    return re.sub(r'[a-zA-Z]+', replace_word, text)


class TTSThread(QThread):
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    warmup_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path=None, parent=None):
        super().__init__(parent)
        self.device = torch.device('cpu')
        self.silero_model = None
        self.piper_voice = None
        self.silero_path = model_path if model_path else DEFAULT_SILERO_PATH
        self.piper_onnx_path = DEFAULT_PIPER_ONNX
        self.piper_json_path = DEFAULT_PIPER_JSON

        self.text_to_speak = ""
        self.speaker = 'kseniya'
        self.silero_sample_rate = 24000
        self.piper_sample_rate = 22050
        self.cached_greeting_sr = 24000

        self._stopped = False
        self._is_warmup = False
        self._play_cached_flag = False
        self.is_whisper = False
        self.greeting_to_precache = ""
        self.cached_greeting_audio = None
        self.warmup_text = "Голосовой ассистент готов к работе."

    def _init_models(self):
        if self.silero_model is None and os.path.exists(self.silero_path):
            try:
                torch.set_num_threads(2)
                importer = torch.package.PackageImporter(self.silero_path)
                self.silero_model = importer.load_pickle("tts_models", "model")
                self.silero_model.to(self.device)
            except Exception as e:
                print(f"[Silero Init Error]: {e}")

        if self.piper_voice is None and os.path.exists(self.piper_onnx_path):
            try:
                self.piper_voice = PiperVoice.load(
                    model_path=self.piper_onnx_path,
                    config_path=self.piper_json_path
                )
                self.piper_sample_rate = self.piper_voice.config.sample_rate
            except Exception as e:
                print(f"[Piper Init Error]: {e}")

    def _process_audio_level(self, audio_np, is_whisper=False):
        if len(audio_np) == 0:
            return audio_np

        peak = np.max(np.abs(audio_np))
        if peak > 0.001:
            audio_np = audio_np / peak

        cfg = load_config()
        vol_percent = cfg.get("voice_volume", 100)
        vol_factor = max(0.0, min(1.0, vol_percent / 100.0))

        if is_whisper:
            vol_factor *= 0.65

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
        cleaned = latin_to_cyrillic(cleaned)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def _synthesize_piper(self, text):
        piper_text = text.lower().strip()
        piper_text = re.sub(r'[^\w\s\.,!\?-]', '', piper_text)
        piper_text = re.sub(r'\s+', ' ', piper_text).strip()

        if not piper_text:
            raise Exception("Текст пуст после фильтрации для Piper.")

        if not piper_text.endswith(('.', '!', '?')):
            piper_text += '.'

        audio_bytes = b"".join(chunk.audio_int16_bytes for chunk in self.piper_voice.synthesize(piper_text))

        if not audio_bytes:
            raise Exception("Piper вернул пустой поток байтов.")

        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return audio_np

    def stop(self):
        self._stopped = True
        try:
            sd.stop()
        except Exception:
            pass
        ym_manager.unduck()
        if self.isRunning():
            self.wait(200)

    def start_warmup(self, greeting_text=None, phrase=None, is_whisper=False):
        self.stop()
        self._is_warmup = True
        self._play_cached_flag = False
        self.is_whisper = is_whisper
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

    def say(self, text, speaker='kseniya', is_whisper=False):
        print(f"[МАЯК 4] TTS say вызван (шепот={is_whisper}): {text}", flush=True)
        self.stop()
        self._is_warmup = False
        self._play_cached_flag = False
        self.text_to_speak = text
        self.speaker = speaker
        self.is_whisper = is_whisper
        self.start()

    def run(self):
        self._stopped = False
        try:
            if not self.silero_model or not self.piper_voice:
                self._init_models()

            if self._is_warmup:
                cleaned_warmup = self._clean_text_for_tts(self.warmup_text)
                if self.silero_model and cleaned_warmup and not self._stopped:
                    with torch.inference_mode():
                        _ = self.silero_model.apply_tts(
                            text=cleaned_warmup,
                            speaker=self.speaker,
                            sample_rate=self.silero_sample_rate
                        )

                if self.greeting_to_precache and not self._stopped:
                    cleaned_greeting = self._clean_text_for_tts(self.greeting_to_precache)
                    if self.is_whisper and self.piper_voice:
                        try:
                            raw_audio = self._synthesize_piper(cleaned_greeting)
                            target_sr = self.piper_sample_rate
                        except Exception as e:
                            print(f"[Piper Warmup Error]: {e}")
                            with torch.inference_mode():
                                audio = self.silero_model.apply_tts(
                                    text=cleaned_greeting,
                                    speaker=self.speaker,
                                    sample_rate=self.silero_sample_rate
                                )
                            raw_audio = audio.numpy()
                            target_sr = self.silero_sample_rate
                    else:
                        with torch.inference_mode():
                            audio = self.silero_model.apply_tts(
                                text=cleaned_greeting,
                                speaker=self.speaker,
                                sample_rate=self.silero_sample_rate
                            )
                        raw_audio = audio.numpy()
                        target_sr = self.silero_sample_rate

                    audio_np = self._process_audio_level(raw_audio, is_whisper=self.is_whisper)
                    padding = np.zeros(int(target_sr * 0.2), dtype=np.float32)
                    self.cached_greeting_audio = np.concatenate([audio_np, padding])
                    self.cached_greeting_sr = target_sr

                self.warmup_finished.emit()
                return

            if self._play_cached_flag:
                self._play_cached_flag = False
                if self.cached_greeting_audio is not None and not self._stopped:
                    target_sr = getattr(self, 'cached_greeting_sr', self.silero_sample_rate)
                    ym_manager.duck()
                    self.speaking_started.emit()
                    sd.play(self.cached_greeting_audio, target_sr)
                    while sd.get_stream() and sd.get_stream().active:
                        if self._stopped:
                            sd.stop()
                            break
                        sd.sleep(40)
                return

            text = self._clean_text_for_tts(self.text_to_speak)
            if not text or self._stopped:
                return

            if self.is_whisper and self.piper_voice:
                try:
                    raw_audio = self._synthesize_piper(text)
                    target_sr = self.piper_sample_rate
                except Exception as e:
                    print(f"[Piper Whisper Error]: {e}")
                    with torch.inference_mode():
                        audio = self.silero_model.apply_tts(
                            text=text,
                            speaker=self.speaker,
                            sample_rate=self.silero_sample_rate
                        )
                    raw_audio = audio.numpy()
                    target_sr = self.silero_sample_rate
            else:
                with torch.inference_mode():
                    audio = self.silero_model.apply_tts(
                        text=text,
                        speaker=self.speaker,
                        sample_rate=self.silero_sample_rate
                    )
                raw_audio = audio.numpy()
                target_sr = self.silero_sample_rate

            if self._stopped:
                return

            audio_np = self._process_audio_level(raw_audio, is_whisper=self.is_whisper)
            padding = np.zeros(int(target_sr * 0.2), dtype=np.float32)
            audio_padded = np.concatenate([audio_np, padding])

            ym_manager.duck()
            self.speaking_started.emit()
            sd.play(audio_padded, target_sr)

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
                ym_manager.unduck()
                self.speaking_finished.emit()