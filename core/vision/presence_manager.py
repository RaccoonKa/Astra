import os
import cv2
import numpy as np
import time
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
        self.unknown_count = 0
        self.unknown_cooldown = 0
        self.ignore_until = 0.0

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._check_timeout)
        self.time_counter = 0

        self.load_owner_faces()

    def set_manual_absence(self, grace_period=12):
        self.is_present = False
        self.time_counter = 0
        self.ignore_until = time.time() + grace_period
        self.timer.stop()

    def load_owner_faces(self):
        appdata_dir = os.environ.get("APPDATA", os.path.expanduser("~"))
        owner_folder = os.path.join(appdata_dir, "Astra", "owner_face")

        cache_file = os.path.join(owner_folder, "encodings_cache.npy")
        self.owner_encodings = []

        if not os.path.exists(owner_folder):
            print(f"[PresenceManager]: Папка owner_face не найдена по пути: {owner_folder}")
            return

        valid_exts = (".jpg", ".jpeg", ".png")
        image_files = [
            os.path.join(owner_folder, f)
            for f in os.listdir(owner_folder)
            if f.lower().endswith(valid_exts)
        ]

        if not image_files:
            print(f"[PresenceManager]: В папке {owner_folder} нет фотографий!")
            return

        if os.path.exists(cache_file):
            try:
                cache_mtime = os.path.getmtime(cache_file)
                newest_img_mtime = max(os.path.getmtime(f) for f in image_files)
                if cache_mtime >= newest_img_mtime:
                    cached = np.load(cache_file, allow_pickle=True)
                    self.owner_encodings = list(cached)
                    return
            except Exception:
                pass

        try:
            import face_recognition
            import cv2
            for file_path in image_files:
                try:
                    img = face_recognition.load_image_file(file_path)
                    h, w = img.shape[:2]
                    if w > 800 or h > 800:
                        scale = 800 / max(w, h)
                        img = cv2.resize(img, (0, 0), fx=scale, fy=scale)

                    encodings = face_recognition.face_encodings(img)
                    if encodings:
                        self.owner_encodings.append(encodings[0])
                except Exception:
                    pass

            if self.owner_encodings:
                np.save(cache_file, np.array(self.owner_encodings))
                print(f"[PresenceManager]: Успешно загружено {len(self.owner_encodings)} лиц владельца!")
        except Exception as e:
            print(f"[PresenceManager]: Ошибка загрузки лиц: {e}")

    def verify_faces(self, frame_rgb):
        try:
            import face_recognition

            small_frame = cv2.resize(frame_rgb, (0, 0), fx=0.5, fy=0.5)
            small_frame = np.ascontiguousarray(small_frame, dtype=np.uint8)
            small_locations = face_recognition.face_locations(small_frame, model="hog")

            valid_locations = []
            for (top, right, bottom, left) in small_locations:
                if (bottom - top) >= 15 and (right - left) >= 15:
                    valid_locations.append((top, right, bottom, left))

            if not valid_locations:
                return False, False

            if not self.owner_encodings:
                return True, True

            h, w = frame_rgb.shape[:2]

            real_locations = [
                (max(0, min(top * 2, h)),
                 max(0, min(right * 2, w)),
                 max(0, min(bottom * 2, h)),
                 max(0, min(left * 2, w)))
                for (top, right, bottom, left) in valid_locations
            ]

            frame_rgb_cont = np.ascontiguousarray(frame_rgb, dtype=np.uint8)
            face_encodings = face_recognition.face_encodings(frame_rgb_cont, real_locations)

            owner_found = False
            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(self.owner_encodings, face_encoding, tolerance=0.50)
                if True in matches:
                    owner_found = True
                    break

            return True, owner_found
        except Exception as e:
            print(f"ОШИБКА В РАСПОЗНАВАНИИ ЛИЦА: {e}")
            return False, False

    def process_face_status(self, face_detected: bool, is_owner: bool = True):
        if time.time() < self.ignore_until:
            return

        if self.unknown_cooldown > 0:
            self.unknown_cooldown -= 1

        if face_detected:
            if not is_owner and self.owner_encodings:
                self.unknown_count += 1
                if self.unknown_count >= 3 and self.unknown_cooldown == 0:
                    self.unknown_count = 0
                    self.unknown_cooldown = 900
                    self.unknown_user_detected.emit()
            else:
                self.time_counter = 0
                self.unknown_count = 0

                if not self.is_present:
                    self.is_present = True
                    self.user_returned.emit()
                    self.timer.stop()
        else:
            self.unknown_count = 0
            if self.is_present and not self.timer.isActive():
                self.timer.start()

    def _check_timeout(self):
        self.time_counter += 1
        if self.time_counter >= self.timeout_seconds:
            self.is_present = False
            self.user_left.emit()
            self.timer.stop()