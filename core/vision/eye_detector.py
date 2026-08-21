from pathlib import Path
from collections import deque
import cv2
import numpy as np
import onnxruntime as ort
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class EyeDetector:
    def __init__(self):
        script_dir = Path(__file__).resolve().parent
        project_dir = script_dir.parent.parent

        candidate_paths = [
            project_dir / "optimized_models" / "eye_model" / "eye_state_model.onnx",
            project_dir / "models" / "eye_model" / "eye_state_model.onnx",
            project_dir / "optimized_models" / "eye_state_model.onnx",
            project_dir / "models" / "eye_state_model.onnx",
        ]

        self.model_path = None
        for p in candidate_paths:
            if p.exists():
                self.model_path = str(p)
                break

        self.session = None
        self.input_name = None

        if self.model_path:
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self.session = ort.InferenceSession(self.model_path, opts, providers=['CPUExecutionProvider'])
                self.input_name = self.session.get_inputs()[0].name
            except Exception:
                pass

        self.history = deque([False] * 5, maxlen=5)

        self.face_landmarker = None
        try:
            task_file = project_dir / "optimized_models" / "face_landmarker" / "face_landmarker.task"

            base_options = python.BaseOptions(model_asset_path=str(task_file))
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.face_landmarker = vision.FaceLandmarker.create_from_options(options)
        except Exception:
            pass

    def is_ready(self):
        return self.session is not None and self.face_landmarker is not None

    def _softmax(self, x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def get_close_probability(self, eye_gray):
        if self.session is None or eye_gray is None or eye_gray.size == 0:
            return None

        try:
            resized = cv2.resize(eye_gray, (32, 32), interpolation=cv2.INTER_AREA)
            normalized = (resized.astype(np.float32) / 255.0 - 0.5) / 0.5
            blob = np.expand_dims(normalized, axis=(0, 1)).astype(np.float32)

            outputs = self.session.run(None, {self.input_name: blob})
            raw_out = outputs[0].flatten()

            if raw_out.size > 1:
                probs = self._softmax(raw_out)
                return float(probs[0])
            else:
                val = float(raw_out[0])
                return 1.0 - val if val <= 1.0 else 0.0
        except Exception:
            return None

    def extract_eye_crop(self, frame_gray, landmarks, indices, w, h):
        x_coords = [int(landmarks[idx].x * w) for idx in indices]
        y_coords = [int(landmarks[idx].y * h) for idx in indices]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        cx = (x_min + x_max) // 2
        cy = (y_min + y_max) // 2

        eye_width = max(x_max - x_min, 10)
        box_size = int(eye_width * 1.6)

        x1 = max(0, cx - box_size // 2)
        y1 = max(0, cy - box_size // 2)
        x2 = min(w, cx + box_size // 2)
        y2 = min(h, cy + box_size // 2)

        if x2 <= x1 or y2 <= y1:
            return None

        return frame_gray[y1:y2, x1:x2]

    def process_frame(self, frame_bgr):
        if not self.is_ready():
            return False, None, 0.0

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        try:
            results = self.face_landmarker.detect(mp_image)
        except Exception:
            return False, None, 0.0

        if not results.face_landmarks:
            return False, None, 0.0

        landmarks = results.face_landmarks[0]
        h, w, _ = frame_bgr.shape
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        LEFT_EYE = [33, 160, 158, 133, 153, 144]
        RIGHT_EYE = [362, 385, 387, 263, 373, 380]

        left_crop = self.extract_eye_crop(frame_gray, landmarks, LEFT_EYE, w, h)
        right_crop = self.extract_eye_crop(frame_gray, landmarks, RIGHT_EYE, w, h)

        valid_probs = []
        if left_crop is not None:
            p_l = self.get_close_probability(left_crop)
            if p_l is not None: valid_probs.append(p_l)

        if right_crop is not None:
            p_r = self.get_close_probability(right_crop)
            if p_r is not None: valid_probs.append(p_r)

        if not valid_probs:
            return True, None, 0.0

        avg_prob_close = sum(valid_probs) / len(valid_probs)

        was_closed_recently = self.history.count(True) >= 1

        if was_closed_recently:
            is_closed_instant = avg_prob_close >= 0.30
        else:
            is_closed_instant = avg_prob_close >= 0.42

        self.history.append(is_closed_instant)

        return True, is_closed_instant, avg_prob_close