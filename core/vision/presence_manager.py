import os
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class PresenceManager(QObject):
    user_left = pyqtSignal()
    user_returned = pyqtSignal()
    unknown_user_detected = pyqtSignal()

    def __init__(self, timeout_seconds=300, parent=None):
        super().__init__(parent)
        self.timeout_seconds = timeout_seconds
        self.is_present = True
        self.owner_encodings = []

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._check_timeout)
        self.time_counter = 0

        self.load_owner_faces()

    def load_owner_faces(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(os.path.dirname(script_dir))
        owner_folder = os.path.join(project_dir, "personal_data", "owner_face")

        self.owner_encodings = []

        if os.path.exists(owner_folder):
            try:
                import face_recognition
                valid_exts = (".jpg", ".jpeg", ".png")
                for file_name in os.listdir(owner_folder):
                    if file_name.lower().endswith(valid_exts):
                        file_path = os.path.join(owner_folder, file_name)
                        img = face_recognition.load_image_file(file_path)
                        encodings = face_recognition.face_encodings(img)
                        if encodings:
                            self.owner_encodings.append(encodings[0])
                if self.owner_encodings:
                    print(f"[PRESENCE]: Загружено {len(self.owner_encodings)} фото владельца.")
            except (ImportError, ModuleNotFoundError):
                print("[PRESENCE INFO]: Модуль 'face_recognition' не установлен в Python. Распознавание лиц по фото временно отключено.")
            except Exception as e:
                print(f"[PRESENCE WARNING]: Ошибка при загрузке фото владельца: {e}")

    def verify_faces(self, frame_rgb):
        if not self.owner_encodings:
            return True, True

        try:
            import face_recognition
            face_locations = face_recognition.face_locations(frame_rgb)
            if not face_locations:
                return False, False

            face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)

            owner_found = False
            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(self.owner_encodings, face_encoding, tolerance=0.5)
                if True in matches:
                    owner_found = True
                    break

            return True, owner_found
        except Exception:
            return True, True

    def process_face_status(self, face_detected: bool, is_owner: bool = True):
        if face_detected:
            self.time_counter = 0

            if not is_owner:
                self.unknown_user_detected.emit()
                return

            if not self.is_present:
                self.is_present = True
                self.user_returned.emit()
                self.timer.stop()
        else:
            if self.is_present and not self.timer.isActive():
                self.timer.start()

    def _check_timeout(self):
        self.time_counter += 1
        if self.time_counter >= self.timeout_seconds:
            self.is_present = False
            self.user_left.emit()
            self.timer.stop()