import os
import sys
import re
import json
import queue
import time
import numpy as np
import sounddevice as sd
import vosk
from PyQt6.QtCore import QThread, pyqtSignal
from core.nlp.asr_corrector import ASRCorrector
from core.utils.config import load_config, get_resource_path
from core.system.actions import ym_manager

FAST_PASS_WORDS = {
    "погода", "погоду", "погоде", "градус", "градусов", "температура", "прогноз",
    "музыка", "музыку", "трек", "песня", "песню", "пауза", "стоп", "плей",
    "включи", "выключи", "открой", "закрой", "запусти", "подруби", "вруби",
    "громкость", "тише", "громче", "звук", "запрет", "обход", "компьютер",
    "пк", "дискорд", "впн", "свет", "люстра", "яркость", "ютуб", "спотифай",
    "расскажи", "умеешь", "делаешь", "дела", "привет", "кто", "что", "как", "зачем", "почему"
}


class STTThread(QThread):
    text_recognized = pyqtSignal(str, bytes)
    listening_state_changed = pyqtSignal(bool)
    wake_word_detected = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path=None, parent=None):
        super().__init__(parent)
        self.followup_timeout = 3.5
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self._running = True
        self.samplerate = 16000
        self.audio_queue = queue.Queue()
        self.manual_trigger_flag = False
        self.is_speaking = False
        self.corrector = ASRCorrector()
        self.model_path = model_path if model_path else get_resource_path("optimized_models", "model_vosk")

        cfg = load_config()
        assistant_name = cfg.get("assistant_name", "астра").lower()

        self.wake_words = {
            assistant_name,
            "астр", "астро", "астру", "астры", "остра", "остру", "остро",
            "быстро", "автора", "пастра", "астрал", "австралия",
            "аста", "асра", "сестра", "костра", "астров"
        }

    def set_speaking(self, state: bool):
        self.is_speaking = state
        if state:
            with self.audio_queue.mutex:
                self.audio_queue.queue.clear()

    def start_followup(self, timeout=3.0):
        self.followup_timeout = timeout
        self.manual_trigger_flag = True

    def _audio_callback(self, indata, frames, time_info, status):
        audio_data = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
        audio_data = audio_data - np.mean(audio_data)

        peak = np.max(np.abs(audio_data))

        if peak > 10.0:
            target_peak = 20000.0
            gain = min(12.0, max(1.0, target_peak / max(peak, 1.0)))
            boosted = np.clip(audio_data * gain, -32768, 32767).astype(np.int16)
        else:
            boosted = audio_data.astype(np.int16)

        self.audio_queue.put(boosted.tobytes())

    def _contains_wake_word(self, text):
        words = text.lower().split()
        for i, word in enumerate(words):
            clean_word = re.sub(r'[^\w]', '', word)
            if clean_word in self.wake_words:
                return True, i
            if clean_word.startswith(("астр", "остр", "астро", "аста", "асра")):
                return True, i
            if clean_word in ["паспорт", "мастер", "остров", "костра", "просто"]:
                return True, i
        return False, -1

    def trigger_manual_listen(self):
        self.manual_trigger_flag = True

    def _smart_correct(self, raw_text: str) -> str:
        clean = raw_text.strip().lower()
        if not clean:
            return ""

        words = clean.split()
        if len(words) <= 8:
            print(f"[STT Фаст-пас]: Короткая фраза ({len(words)} сл.) -> без задержки", flush=True)
            return clean

        word_set = set(re.findall(r'\w+', clean))
        if word_set & FAST_PASS_WORDS:
            print(f"[STT Фаст-пас]: Найдено триггер-слово -> без задержки", flush=True)
            return clean

        t0 = time.perf_counter()
        print(f"[STT]: Запуск корректора на CPU для: '{raw_text}'", flush=True)
        corrected = self.corrector.correct(raw_text)
        print(f"[STT]: Корректор отработал за {time.perf_counter() - t0:.2f}с -> '{corrected}'", flush=True)
        return corrected

    def run(self):
        try:
            vosk.SetLogLevel(-1)
            model = vosk.Model(self.model_path)
            recognizer = vosk.KaldiRecognizer(model, self.samplerate)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка загрузки модели Vosk: {e}")
            return

        try:
            stream = sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=4000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback
            )
        except Exception as e:
            self.error_occurred.emit(f"Ошибка микрофона: {e}")
            return

        active_mode = False
        active_start_time = 0.0
        utterance_buffer = bytearray()
        wake_signaled = False

        with stream:
            self.listening_state_changed.emit(False)

            while self._running:
                if self.is_speaking:
                    try:
                        self.audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        pass
                    continue

                if self.manual_trigger_flag:
                    self.manual_trigger_flag = False
                    active_mode = True
                    active_start_time = time.time()
                    recognizer.Reset()
                    utterance_buffer.clear()
                    wake_signaled = False
                    ym_manager.duck()
                    self.listening_state_changed.emit(True)

                if active_mode and (time.time() - active_start_time > self.followup_timeout):
                    active_mode = False
                    utterance_buffer.clear()
                    wake_signaled = False
                    ym_manager.unduck(100)
                    self.listening_state_changed.emit(False)

                try:
                    data = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                utterance_buffer.extend(data)

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    phrase_audio = bytes(utterance_buffer)
                    utterance_buffer.clear()
                    wake_signaled = False

                    if not text:
                        continue

                    main_win = self.parent()
                    is_alarm_ringing = False
                    if main_win and hasattr(main_win, 'command_parser'):
                        is_alarm_ringing = main_win.command_parser.reminder_manager.is_ringing

                    if is_alarm_ringing:
                        self.text_recognized.emit(text, phrase_audio)
                        continue

                    has_wake, wake_idx = self._contains_wake_word(text)

                    if has_wake:
                        self.wake_word_detected.emit()
                        self.followup_timeout = 4.5
                        words = text.split()
                        raw_command = " ".join(words[wake_idx + 1:]).strip()
                        if raw_command:
                            ym_manager.duck()
                            command = self._smart_correct(raw_command)
                            self.text_recognized.emit(command, phrase_audio)
                            active_mode = False
                            self.listening_state_changed.emit(False)
                        else:
                            active_mode = True
                            active_start_time = time.time()
                            recognizer.Reset()
                            ym_manager.duck()
                            self.listening_state_changed.emit(True)
                    elif active_mode:
                        command = self._smart_correct(text)
                        self.text_recognized.emit(command, phrase_audio)
                        active_mode = False
                        self.listening_state_changed.emit(False)
                else:
                    partial_res = json.loads(recognizer.PartialResult())
                    partial_text = partial_res.get("partial", "").strip()

                    if active_mode:
                        if partial_text:
                            active_start_time = time.time()
                    else:
                        if partial_text and not wake_signaled:
                            has_wake, _ = self._contains_wake_word(partial_text)
                            if has_wake:
                                wake_signaled = True
                                self.wake_word_detected.emit()
                                ym_manager.duck()
                                self.listening_state_changed.emit(True)

    def stop_thread(self):
        self._running = False
        ym_manager.unduck()
        self.wait()