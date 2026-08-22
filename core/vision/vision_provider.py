import time
import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from core.utils.config import load_config


class VisionThread(QThread):
    frame_processed = pyqtSignal(np.ndarray)
    face_detected_signal = pyqtSignal(bool, bool)
    gesture_detected_signal = pyqtSignal(str)
    deep_drowsiness_signal = pyqtSignal()
    frequent_blinking_signal = pyqtSignal()

    def __init__(self, camera_index=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.is_running = True

        self.gesture_detector = None
        self.eye_detector = None

        self.frame_counter = 0
        self.last_gesture = None
        self.gesture_cooldown = 0

        self.sleep_start_time = None
        self.last_closed_time = 0.0
        self.blink_start_time = None
        self.blink_timestamps = []
        self.drowsiness_cooldown_until = 0.0
        self.cached_modules = {"vision": True, "gestures": True}
        self.is_ready_for_blink = True

        self.last_face_found = False
        self.last_is_owner = True

    def _update_modules_config(self):
        try:
            cfg = load_config()
            self.cached_modules = cfg.get("modules", {})
        except Exception:
            pass

    def run(self):
        self._update_modules_config()
        cap = None

        while self.is_running:
            if self.frame_counter % 30 == 0:
                self._update_modules_config()

            face_rec_enabled = self.cached_modules.get("face_recognition", self.cached_modules.get("vision", False))
            eye_enabled = self.cached_modules.get("eye_tracking", self.cached_modules.get("vision", False))
            gestures_enabled = self.cached_modules.get("gestures", False)

            if not (face_rec_enabled or eye_enabled or gestures_enabled):
                if cap is not None and cap.isOpened():
                    cap.release()
                    cap = None

                self.eye_detector = None
                self.gesture_detector = None

                self.msleep(500)
                continue

            if eye_enabled and self.eye_detector is None:
                try:
                    from core.vision.eye_detector import EyeDetector
                    self.eye_detector = EyeDetector()
                except Exception:
                    pass
            elif not eye_enabled and self.eye_detector is not None:
                self.eye_detector = None

            if gestures_enabled and self.gesture_detector is None:
                try:
                    from core.vision.gesture_detector import GestureDetector
                    self.gesture_detector = GestureDetector()
                except Exception:
                    pass
            elif not gestures_enabled and self.gesture_detector is not None:
                self.gesture_detector = None

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
                self.msleep(20)
                continue

            self.frame_counter += 1
            now = time.time()

            fast_face_found = False

            if eye_enabled and self.eye_detector and self.eye_detector.is_ready():
                fast_face_found, is_instant_closed, prob = self.eye_detector.process_frame(frame)

                if fast_face_found and is_instant_closed is not None:
                    if is_instant_closed:
                        if self.is_ready_for_blink and self.blink_start_time is None:
                            self.blink_start_time = now
                            self.is_ready_for_blink = False

                        if self.sleep_start_time is None:
                            self.sleep_start_time = now
                        self.last_closed_time = now

                        sleep_dur = now - self.sleep_start_time
                        if sleep_dur >= 6.0 and now > self.drowsiness_cooldown_until:
                            self.deep_drowsiness_signal.emit()
                            self.drowsiness_cooldown_until = now + 30.0
                            self.sleep_start_time = None
                            self.blink_start_time = None
                    else:
                        self.is_ready_for_blink = True

                        if self.blink_start_time is not None:
                            blink_dur = now - self.blink_start_time
                            if 0.02 <= blink_dur <= 0.60:
                                self.blink_timestamps.append(now)
                            self.blink_start_time = None

                        if self.sleep_start_time and (now - self.last_closed_time > 0.5):
                            self.sleep_start_time = None

                    self.blink_timestamps = [t for t in self.blink_timestamps if now - t <= 10.0]

                    if len(self.blink_timestamps) >= 15 and now > self.drowsiness_cooldown_until:
                        self.frequent_blinking_signal.emit()
                        self.drowsiness_cooldown_until = now + 25.0
                        self.blink_timestamps.clear()

            if face_rec_enabled:
                presence_mgr = getattr(self.parent(), 'presence_manager', None)
                if presence_mgr:
                    if self.frame_counter % 15 == 0:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        f_found, i_owner = presence_mgr.verify_faces(frame_rgb)
                        self.last_face_found = f_found
                        self.last_is_owner = i_owner

                    emit_face = fast_face_found if eye_enabled else self.last_face_found
                    self.face_detected_signal.emit(emit_face, self.last_is_owner)
            elif eye_enabled:
                self.face_detected_signal.emit(fast_face_found, True)

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
            self.msleep(20)

        if cap is not None and cap.isOpened():
            cap.release()

    def stop(self):
        self.is_running = False
        self.wait()