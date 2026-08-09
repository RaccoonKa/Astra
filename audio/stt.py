import json
import pyaudio
from vosk import Model, KaldiRecognizer
from PyQt6.QtCore import QThread, pyqtSignal


class STTThread(QThread):
    text_recognized = pyqtSignal(str)
    listening_state_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, model_path="models/model_vosk", parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.is_listening = False
        self._running = True

    def run(self):
        try:
            model = Model(self.model_path)
            recognizer = KaldiRecognizer(model, 16000)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка загрузки модели Vosk: {e}")
            return

        p = pyaudio.PyAudio()
        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8000
            )
        except Exception as e:
            self.error_occurred.emit(f"Ошибка микрофона: {e}")
            p.terminate()
            return

        stream.start_stream()

        while self._running:
            if self.is_listening:
                data = stream.read(4000, exception_on_overflow=False)
                if len(data) == 0:
                    continue

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        self.text_recognized.emit(text)
            else:
                self.msleep(100)

        stream.stop_stream()
        stream.close()
        p.terminate()

    def start_listening(self):
        self.is_listening = True
        self.listening_state_changed.emit(True)

    def stop_listening(self):
        self.is_listening = False
        self.listening_state_changed.emit(False)

    def toggle_listening(self):
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()

    def stop_thread(self):
        self._running = False
        self.wait()