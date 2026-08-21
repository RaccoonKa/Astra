import os
import json
import queue
import time
import sounddevice as sd
import vosk
from PyQt6.QtCore import QThread, pyqtSignal
from core.nlp.asr_corrector import ASRCorrector


class STTThread(QThread):
    text_recognized = pyqtSignal(str, bytes)
    listening_state_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path="optimized_models/model_vosk", parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self._running = True
        self.samplerate = 16000
        self.audio_queue = queue.Queue()
        self.manual_trigger_flag = False
        self.is_speaking = False
        self.corrector = ASRCorrector()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config.template.json")
        assistant_name = "астра"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    assistant_name = cfg.get("assistant_name", "астра").lower()
            except Exception:
                pass

        self.wake_words = {
            assistant_name,
            "астр", "астро", "астру", "астры", "остра", "остру",
            "быстро", "автора", "пастра", "астрал", "австралия"
        }

    def set_speaking(self, state: bool):
        self.is_speaking = state
        if state:
            with self.audio_queue.mutex:
                self.audio_queue.queue.clear()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            pass
        self.audio_queue.put(bytes(indata))

    def _contains_wake_word(self, text):
        words = text.lower().split()
        for i, word in enumerate(words):
            if word in self.wake_words:
                return True, i
        return False, -1

    def trigger_manual_listen(self):
        self.manual_trigger_flag = True

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
                blocksize=8000,
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
                    self.listening_state_changed.emit(True)

                if active_mode and (time.time() - active_start_time > 4.0):
                    active_mode = False
                    utterance_buffer.clear()
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

                    if not text:
                        continue

                    has_wake, wake_idx = self._contains_wake_word(text)

                    if has_wake:
                        words = text.split()
                        raw_command = " ".join(words[wake_idx + 1:]).strip()
                        if raw_command:
                            command = self.corrector.correct(raw_command)
                            self.text_recognized.emit(command, phrase_audio)
                            active_mode = False
                            self.listening_state_changed.emit(False)
                        else:
                            active_mode = True
                            active_start_time = time.time()
                            recognizer.Reset()
                            self.listening_state_changed.emit(True)
                    elif active_mode:
                        command = self.corrector.correct(text)
                        self.text_recognized.emit(command, phrase_audio)
                        active_mode = False
                        self.listening_state_changed.emit(False)

    def stop_thread(self):
        self._running = False
        self.wait()