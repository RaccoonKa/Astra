import os
import json
import queue
import sounddevice as sd
import vosk


class SpeechListener:
    def __init__(self, device_id=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        config_path = os.path.join(base_dir, "config.template.json")
        assistant_name = "Aстра"
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

        model_path = os.path.join(base_dir, "models", "model_vosk")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Модель Vosk не найдена по адресу: {model_path}")

        vosk.SetLogLevel(-1)
        self.model = vosk.Model(model_path)
        self.samplerate = 16000
        self.audio_queue = queue.Queue()
        self.device_id = device_id

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"[AUDIO WARNING]: {status}", flush=True)
        self.audio_queue.put(bytes(indata))

    def _contains_wake_word(self, text):
        words = text.lower().split()
        for i, word in enumerate(words):
            if word in self.wake_words:
                return True, i
        return False, -1

    def listen_loop(self, on_command_detected):
        print("\n--- Доступные аудиоустройства ---")
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        for idx, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                is_def = " (ПО УМОЛЧАНИЮ)" if idx == default_input else ""
                print(f"[{idx}] {dev['name']}{is_def}")
        print("---------------------------------\n")

        recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)

        with sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=8000,
                device=self.device_id,
                dtype="int16",
                channels=1,
                callback=self._audio_callback
        ):
            print(f"[INFO]: Слушатель запущен! Произнеси 'Астра'...")

            active_mode = False

            while True:
                data = self.audio_queue.get()

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()

                    if not text:
                        continue

                    print(f"[СЛЫШУ]: {text}")

                    has_wake, wake_idx = self._contains_wake_word(text)

                    if has_wake:
                        words = text.split()
                        command = " ".join(words[wake_idx + 1:]).strip()
                        if command:
                            print(f"[КОМАНДА]: {command}")
                            on_command_detected(command)
                            active_mode = False
                        else:
                            print("[АКТИВАЦИЯ]: Услышала имя! Слушаю команду...")
                            active_mode = True
                    elif active_mode:
                        print(f"[КОМАНДА В АКТИВНОМ РЕЖИМЕ]: {text}")
                        on_command_detected(text)
                        active_mode = False


if __name__ == "__main__":
    from core.nlp.command_parser import CommandParser

    parser = CommandParser()


    def handle_command(text):
        response = parser.process_command(text)
        print(f"[ОТВЕТ АСТРЫ]: {response}\n")


    listener = SpeechListener()
    listener.listen_loop(handle_command)