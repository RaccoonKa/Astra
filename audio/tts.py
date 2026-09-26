import os
import sys
import re
import json
import queue
import threading
import numpy as np
import sounddevice as sd
import onnxruntime as ort
from PyQt6.QtCore import QThread, pyqtSignal
from piper.voice import PiperVoice
from core.utils.config import get_resource_path, load_config
from core.system.actions import ym_manager

ort.set_default_logger_severity(3)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAIN_VOICE_ONNX = get_resource_path("optimized_models", "voice_tts", "astra_voice_int8.onnx")
MAIN_VOICE_JSON = get_resource_path("optimized_models", "voice_tts", "astra_voice_int8.onnx.json")

WHISPER_VOICE_ONNX = get_resource_path("optimized_models", "whisper_tts", "astra_whisper_int8.onnx")
WHISPER_VOICE_JSON = get_resource_path("optimized_models", "whisper_tts", "astra_whisper_int8.onnx.json")

DICT_FILE_PATH = get_resource_path("core", "utils", "pronunciation_dict.json")
CUSTOM_DICTIONARY = {}
COMPILED_DICT_REGEX = None


def _load_pronunciation_dictionary():
    global CUSTOM_DICTIONARY, COMPILED_DICT_REGEX
    if os.path.exists(DICT_FILE_PATH):
        try:
            with open(DICT_FILE_PATH, "r", encoding="utf-8") as f:
                CUSTOM_DICTIONARY = json.load(f)
            sorted_keys = sorted(CUSTOM_DICTIONARY.keys(), key=len, reverse=True)
            escaped_keys = [re.escape(k) for k in sorted_keys]
            COMPILED_DICT_REGEX = re.compile(r'(?<!\w)(' + '|'.join(escaped_keys) + r')(?!\w)', flags=re.IGNORECASE)
        except Exception as e:
            print(f"[Pronunciation Dict Error]: {e}")
            CUSTOM_DICTIONARY = {}
            COMPILED_DICT_REGEX = None


_load_pronunciation_dictionary()


def get_tts_execution_providers():
    available = ort.get_available_providers()
    if "DmlExecutionProvider" in available:
        return ["DmlExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def load_piper_voice(model_path, config_path):
    voice = PiperVoice.load(model_path=model_path, config_path=config_path)
    providers = get_tts_execution_providers()

    if "DmlExecutionProvider" in providers:
        try:
            sess_opts = ort.SessionOptions()
            sess_opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            voice.session = ort.InferenceSession(
                str(model_path),
                sess_options=sess_opts,
                providers=providers
            )
            print(f"[TTS]: Модель {os.path.basename(model_path)} запущена на GPU (DirectML)")
        except Exception as e:
            print(f"[TTS Warning]: DirectML недоступен для {os.path.basename(model_path)} ({e}). Откат на CPU.")
    else:
        print(f"[TTS]: Видеокарта с DirectML не найдена. {os.path.basename(model_path)} работает на CPU.")

    return voice


def apply_pronunciation_and_translit(text: str) -> str:
    if not text:
        return ""

    if COMPILED_DICT_REGEX:
        def dict_sub(match):
            key = match.group(0).lower()
            return CUSTOM_DICTIONARY.get(key, match.group(0))
        text = COMPILED_DICT_REGEX.sub(dict_sub, text)

    def translit_fallback(match):
        w = match.group(0).lower()
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

    return re.sub(r'[a-zA-Z]+', translit_fallback, text)


class TTSThread(QThread):
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    warmup_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_voice = None
        self.whisper_voice = None

        self.text_to_speak = ""
        self.is_whisper = False
        self._stopped = False
        self._is_warmup = False
        self._play_cached_flag = False

        self.greeting_to_precache = ""
        self.cached_greeting_audio = None
        self.cached_greeting_sr = 22050
        self.warmup_text = "готов"

    def _init_models(self):
        if self.main_voice is None and os.path.exists(MAIN_VOICE_ONNX):
            try:
                self.main_voice = load_piper_voice(MAIN_VOICE_ONNX, MAIN_VOICE_JSON)
            except Exception as e:
                print(f"[Main Piper Init Error]: {e}")

        if self.whisper_voice is None and os.path.exists(WHISPER_VOICE_ONNX):
            try:
                self.whisper_voice = load_piper_voice(WHISPER_VOICE_ONNX, WHISPER_VOICE_JSON)
            except Exception as e:
                print(f"[Whisper Piper Init Error]: {e}")

    def _clean_text_for_tts(self, text):
        if not text:
            return ""

        def _expand_time(m):
            h = int(m.group(1))
            minute = int(m.group(2))
            if minute == 0:
                return f"{h} часов"
            elif minute < 10:
                return f"{h} ноль {minute}"
            else:
                return f"{h} {minute}"

        text = re.sub(r'\b(\d{1,2}):(\d{2})\b', _expand_time, text)

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
        cleaned = apply_pronunciation_and_translit(cleaned)

        cleaned = re.sub(r'\+([аеёиоуыэюяАЕЁИОУЫЭЮЯ])', r'\1' + '\u0301', cleaned)
        cleaned = re.sub(r'([аеёиоуыэюяАЕЁИОУЫЭЮЯ])\+', r'\1' + '\u0301', cleaned)

        cleaned = cleaned.lower().strip()
        cleaned = cleaned.replace('!', '.').replace(';', ',').replace('—', '-')
        cleaned = re.sub(r'\.+', '.', cleaned)
        cleaned = re.sub(r'[^\w\s\.,!?\-\u0301]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if cleaned and not cleaned.endswith(('.', '?')):
            cleaned += '.'

        return cleaned

    def _get_volume_factor(self, is_whisper=False):
        cfg = load_config()
        vol_percent = cfg.get("voice_volume", 100)
        vol_factor = max(0.0, min(1.0, vol_percent / 100.0))
        if is_whisper:
            vol_factor *= 0.65
        return vol_factor

    def _play_stream(self, voice, text, is_whisper=False):
        vol_factor = self._get_volume_factor(is_whisper=is_whisper)
        sample_rate = voice.config.sample_rate

        ym_manager.duck()
        self.speaking_started.emit()

        sentences = [s.strip() for s in re.split(r'(?<=[.?])\s+', text) if s.strip()]
        if not sentences:
            sentences = [text]

        pause_bytes = np.zeros(int(sample_rate * 0.25), dtype=np.int16).tobytes()
        silence_padding = np.zeros(int(sample_rate * 0.15), dtype=np.int16).tobytes()

        audio_queue = queue.Queue(maxsize=300)

        def producer():
            for idx, sentence in enumerate(sentences):
                if self._stopped:
                    break

                for chunk in voice.synthesize(sentence):
                    if self._stopped:
                        break
                    chunk_bytes = chunk.audio_int16_bytes
                    if chunk_bytes:
                        audio_queue.put(chunk_bytes)

                if idx < len(sentences) - 1 and not self._stopped:
                    audio_queue.put(pause_bytes)

            audio_queue.put(None)

        producer_thread = threading.Thread(target=producer, daemon=True)
        producer_thread.start()

        try:
            with sd.RawOutputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
                while not self._stopped:
                    try:
                        chunk_bytes = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        if not producer_thread.is_alive():
                            break
                        continue

                    if chunk_bytes is None:
                        break

                    if abs(vol_factor - 1.0) > 0.01:
                        data_np = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)
                        scaled_bytes = (data_np * vol_factor).astype(np.int16).tobytes()
                        stream.write(scaled_bytes)
                    else:
                        stream.write(chunk_bytes)

                if not self._stopped:
                    stream.write(silence_padding)
        finally:
            ym_manager.unduck()
            self.speaking_finished.emit()

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

    def say(self, text, is_whisper=False, speaker=None):
        self.stop()
        self._is_warmup = False
        self._play_cached_flag = False
        self.text_to_speak = text
        self.is_whisper = is_whisper
        self.start()

    def run(self):
        self._stopped = False
        try:
            if not self.main_voice or not self.whisper_voice:
                self._init_models()

            if self._is_warmup:
                cleaned_warmup = self._clean_text_for_tts(self.warmup_text)
                for v in [self.main_voice, self.whisper_voice]:
                    if v and cleaned_warmup:
                        for _ in v.synthesize(cleaned_warmup):
                            break

                if self.greeting_to_precache and not self._stopped:
                    cleaned_greeting = self._clean_text_for_tts(self.greeting_to_precache)
                    target_voice = self.whisper_voice if (self.is_whisper and self.whisper_voice) else self.main_voice

                    if target_voice and cleaned_greeting:
                        target_sr = target_voice.config.sample_rate
                        greeting_sentences = [s.strip() for s in re.split(r'(?<=[.?])\s+', cleaned_greeting) if s.strip()]
                        if not greeting_sentences:
                            greeting_sentences = [cleaned_greeting]

                        audio_parts = []
                        pause_np = np.zeros(int(target_sr * 0.25), dtype=np.float32)
                        vol_factor = self._get_volume_factor(is_whisper=self.is_whisper)

                        for g_idx, g_sent in enumerate(greeting_sentences):
                            g_chunks = b"".join(c.audio_int16_bytes for c in target_voice.synthesize(g_sent))
                            if g_chunks:
                                part_np = np.frombuffer(g_chunks, dtype=np.int16).astype(np.float32) / 32768.0
                                audio_parts.append(part_np * vol_factor)
                                if g_idx < len(greeting_sentences) - 1:
                                    audio_parts.append(pause_np)

                        if audio_parts:
                            padding = np.zeros(int(target_sr * 0.15), dtype=np.float32)
                            self.cached_greeting_audio = np.concatenate(audio_parts + [padding]).astype(np.float32)
                            self.cached_greeting_sr = target_sr

                self.warmup_finished.emit()
                return

            if self._play_cached_flag:
                self._play_cached_flag = False
                if self.cached_greeting_audio is not None and not self._stopped:
                    ym_manager.duck()
                    self.speaking_started.emit()
                    sd.play(self.cached_greeting_audio, self.cached_greeting_sr)
                    while sd.get_stream() and sd.get_stream().active:
                        if self._stopped:
                            sd.stop()
                            break
                        sd.sleep(40)
                    ym_manager.unduck()
                    self.speaking_finished.emit()
                return

            text = self._clean_text_for_tts(self.text_to_speak)
            if not text or self._stopped:
                return

            target_voice = self.whisper_voice if (self.is_whisper and self.whisper_voice) else self.main_voice
            if not target_voice:
                return

            self._play_stream(target_voice, text, is_whisper=self.is_whisper)

        except Exception as e:
            print(f"[TTS Stream Error]: {e}")
            self.error_occurred.emit(str(e))
            if self._is_warmup:
                self.warmup_finished.emit()
        finally:
            if not self._is_warmup and not self._play_cached_flag:
                ym_manager.unduck()