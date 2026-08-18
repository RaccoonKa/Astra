import os
import json
import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from core.vision.gesture_detector import GestureDetector


class VisionThread(QThread):
    frame_processed = pyqtSignal(np.ndarray)
    face_detected_signal = pyqtSignal(bool)
    gesture_detected_signal = pyqtSignal(str)

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.is_running = True
        self.gesture_detector = None
        self.frame_counter = 0
        self.last_gesture = None
        self.gesture_cooldown = 0
        self.face_cascade = None

        try:
            if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'):
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
                if self.face_cascade.empty():
                    self.face_cascade = None
        except Exception as e:
            print(f"[VISION WARNING]: Не удалось загрузить каскад лиц: {e}")
            self.face_cascade = None

    def _get_modules_config(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "personal_data", "configs", "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return cfg.get("modules", {})
            except Exception:
                pass
        return {"vision": True, "gestures": True}

    def run(self):
        try:
            self.gesture_detector = GestureDetector()
        except Exception as e:
            print(f"[GESTURE INIT ERROR]: {e}")

        cap = None

        while self.is_running:
            modules = self._get_modules_config()
            vision_enabled = modules.get("vision", True)
            gestures_enabled = modules.get("gestures", True)

            if not vision_enabled and not gestures_enabled:
                if cap is not None and cap.isOpened():
                    cap.release()
                    cap = None
                self.msleep(500)
                continue

            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                else:
                    self.msleep(1000)
                    continue

            ret, frame = cap.read()
            if not ret or frame is None or frame.size == 0:
                self.msleep(30)
                continue

            self.frame_counter += 1

            if vision_enabled:
                if self.frame_counter % 5 == 0:
                    if self.face_cascade is not None:
                        try:
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            faces = self.face_cascade.detectMultiScale(
                                gray,
                                scaleFactor=1.2,
                                minNeighbors=5,
                                minSize=(60, 60)
                            )
                            self.face_detected_signal.emit(len(faces) > 0)
                        except Exception:
                            self.face_detected_signal.emit(True)
                    else:
                        self.face_detected_signal.emit(True)

            if gestures_enabled:
                if self.gesture_cooldown > 0:
                    self.gesture_cooldown -= 1
                elif self.frame_counter % 3 == 0 and self.gesture_detector is not None:
                    gesture = self.gesture_detector.process_frame(frame)
                    if gesture and gesture != self.last_gesture:
                        self.gesture_detected_signal.emit(gesture)
                        self.last_gesture = gesture
                        self.gesture_cooldown = 20
                    elif not gesture:
                        self.last_gesture = None

            self.frame_processed.emit(frame)
            self.msleep(33)

        if cap is not None and cap.isOpened():
            cap.release()

    def stop(self):
        self.is_running = False
        self.wait()