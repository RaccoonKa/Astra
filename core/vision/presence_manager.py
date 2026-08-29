import os
import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from core.utils.config import get_user_data_path


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
        owner_folder = os.path.normpath(get_user_data_path("..", "owner_face"))
        cache_file = os.path.join(owner_folder, "encodings_cache.npy")
        self.owner_encodings = []

        if not os.path.exists(owner_folder):
            return

        valid_exts = (".jpg", ".jpeg", ".png")
        image_files = [
            os.path.join(owner_folder, f)
            for f in os.listdir(owner_folder)
            if f.lower().endswith(valid_exts)
        ]

        if not image_files:
            return

        if os.path.exists(cache_file):
            try:
                cache_mtime = os.path.getmtime(cache_file)
                newest_img_mtime = max(os.path.getmtime(f) for f in image_files)
                if cache_mtime >= newest_img_mtime:
                    cached = np.load(cache_file, allow_pickle=True)
                    self.owner_encodings = list(cached)
                    print(f"[PRESENCE]: Загружено {len(self.owner_encodings)} фото владельца из кэша (0.01с).")
                    return
            except Exception:
                pass

        try:
            import face_recognition
            for file_path in image_files:
                img = face_recognition.load_image_file(file_path)
                encodings = face_recognition.face_encodings(img)
                if encodings:
                    self.owner_encodings.append(encodings[0])

            if self.owner_encodings:
                np.save(cache_file, np.array(self.owner_encodings, dtype=object))
                print(f"[PRESENCE]: Закодировано и закэшировано {len(self.owner_encodings)} фото владельца.")
        except (ImportError, ModuleNotFoundError):
            print("[PRESENCE INFO]: Модуль 'face_recognition' не установлен.")
        except Exception as e:
            print(f"[PRESENCE WARNING]: Ошибка при загрузке фото: {e}")

    def verify_faces(self, frame_rgb):
        if not self.owner_encodings:
            return True, True

        try:
            import face_recognition

            small_frame = cv2.resize(frame_rgb, (0, 0), fx=0.5, fy=0.5)
            small_locations = face_recognition.face_locations(small_frame, model="hog")

            if not small_locations:
                return False, False

            real_locations = [
                (top * 2, right * 2, bottom * 2, left * 2)
                for (top, right, bottom, left) in small_locations
            ]

            face_encodings = face_recognition.face_encodings(frame_rgb, real_locations)

            owner_found = False
            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(self.owner_encodings, face_encoding, tolerance=0.50)
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