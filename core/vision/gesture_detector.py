# Файл считывания положения фаланг пальцев.

import os
import cv2
import urllib.request
import numpy as np
import math
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


def get_hand_model_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(os.path.dirname(script_dir))
    models_dir = os.path.join(project_dir, "optimized_models", "hand_landmaker")
    os.makedirs(models_dir, exist_ok=True)

    model_path = os.path.join(models_dir, "hand_landmarker.task")

    if os.path.exists(model_path) and os.path.getsize(model_path) < 5000000:
        try:
            os.remove(model_path)
        except Exception:
            pass

    if not os.path.exists(model_path):
        url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
        try:
            urllib.request.urlretrieve(url, model_path)
        except Exception as e:
            print(f"[MODEL DOWNLOAD ERROR]: {e}")

    return model_path


class GestureDetector:
    def __init__(self):
        model_path = get_hand_model_path()
        if not os.path.exists(model_path) or os.path.getsize(model_path) < 5000000:
            raise FileNotFoundError("Модель hand_landmarker.task не загружена или повреждена.")

        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
        self.clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

    def _enhance_light(self, small_bgr):
        lab = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self.clahe.apply(l)
        enhanced_lab = cv2.merge((l, a, b))
        return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)

    def _dist(self, p1, p2):
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

    def process_frame(self, frame_bgr):
        if frame_bgr is None or frame_bgr.size == 0:
            return None

        try:
            enhanced_frame = self._enhance_light(frame_bgr)
            frame_rgb = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2RGB)
            frame_rgb = np.ascontiguousarray(frame_rgb, dtype=np.uint8)

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            detection_result = self.detector.detect(mp_image)

            if not detection_result or not detection_result.hand_landmarks:
                return None

            lm = detection_result.hand_landmarks[0]
            wrist = lm[0]

            index_folded = self._dist(lm[8], wrist) < self._dist(lm[6], wrist)
            middle_folded = self._dist(lm[12], wrist) < self._dist(lm[10], wrist)
            ring_folded = self._dist(lm[16], wrist) < self._dist(lm[14], wrist)
            pinky_folded = self._dist(lm[20], wrist) < self._dist(lm[18], wrist)

            index_open = not index_folded
            middle_open = not middle_folded
            ring_open = not ring_folded
            pinky_open = not pinky_folded

            # Кулак: все 4 пальца сжаты к ладони
            if index_folded and middle_folded and ring_folded and pinky_folded:
                return "fist"

            # Победа (V): указательный и средний открыты, остальные сжаты
            if index_open and middle_open and ring_folded and pinky_folded:
                return "victory"

            # Указательный палец вверх
            if index_open and middle_folded and ring_folded and pinky_folded:
                return "pointing"

            # Открытая ладонь: все пальцы открыты
            if index_open and middle_open and ring_open and pinky_open:
                return "open_palm"

            # Лайк
            thumb_up = lm[4].y < lm[3].y and lm[3].y < lm[2].y
            if thumb_up and index_folded and middle_folded and ring_folded and pinky_folded:
                return "thumbs_up"

        except Exception:
            return None

        return None