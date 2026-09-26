import os
import json
import numpy as np
import onnxruntime as ort
from core.utils.config import get_resource_path, get_user_data_path


def _get_mel_filters(sr=16000, n_fft=512, n_mels=80, fmin=20.0, fmax=7600.0):
    def hz_to_mel(hz):
        return 2595.0 * np.log10(1.0 + hz / 700.0)

    def mel_to_hz(mel):
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    min_mel = hz_to_mel(fmin)
    max_mel = hz_to_mel(fmax)
    mels = np.linspace(min_mel, max_mel, n_mels + 2)
    hz_pts = mel_to_hz(mels)
    bins = np.floor((n_fft + 1) * hz_pts / sr).astype(int)

    weights = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for i in range(n_mels):
        left = bins[i]
        center = bins[i + 1]
        right = bins[i + 2]

        if center > left:
            weights[i, left:center] = (np.arange(left, center) - left) / (center - left)
        if right > center:
            weights[i, center:right] = (right - np.arange(center, right)) / (right - center)

    return weights


def _extract_fbank(signal, sr=16000, n_mels=80, win_len=400, hop_len=160, n_fft=512):
    if len(signal) < win_len:
        signal = np.pad(signal, (0, win_len - len(signal)), mode='constant')

    emphasized = np.append(signal[0], signal[1:] - 0.97 * signal[:-1])
    num_frames = 1 + int((len(emphasized) - win_len) / hop_len)

    frames = np.lib.stride_tricks.as_strided(
        emphasized,
        shape=(num_frames, win_len),
        strides=(emphasized.strides[0] * hop_len, emphasized.strides[0])
    ).copy()

    frames *= np.hamming(win_len)
    mag_frames = np.abs(np.fft.rfft(frames, n_fft)) ** 2

    filters = _get_mel_filters(sr=sr, n_fft=n_fft, n_mels=n_mels)
    mel_energies = np.dot(mag_frames, filters.T)
    mel_energies = np.maximum(mel_energies, 1e-6)
    log_mel = np.log(mel_energies)

    return (log_mel - np.mean(log_mel, axis=0, keepdims=True)).astype(np.float32)


class SpeakerVerifier:
    def __init__(self, model_path=None, threshold=0.70):
        self.threshold = threshold
        self.profiles_path = get_user_data_path("voice_profiles.json")
        self.temp_enrollment_samples = []

        if model_path is None:
            model_path = get_resource_path("optimized_models", "voiceprint", "tiny_ecapa.onnx")

        self.session = None
        self.input_name = None
        self.input_shape = None

        if os.path.exists(model_path):
            try:
                session_options = ort.SessionOptions()
                session_options.intra_op_num_threads = 2
                session_options.inter_op_num_threads = 1
                session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

                self.session = ort.InferenceSession(
                    model_path,
                    sess_options=session_options,
                    providers=["CPUExecutionProvider"]
                )
                self.input_name = self.session.get_inputs()[0].name
                self.input_shape = self.session.get_inputs()[0].shape
                print(f"[SpeakerVerifier]: ECAPA загружена (вход: {self.input_name}, форма: {self.input_shape})", flush=True)
            except Exception as e:
                print(f"[SpeakerVerifier Init Error]: {e}", flush=True)

        self.profiles = self._load_profiles()

    def _load_profiles(self):
        if os.path.exists(self.profiles_path):
            try:
                with open(self.profiles_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"owner": None, "users": {}}

    def _save_profiles(self):
        os.makedirs(os.path.dirname(self.profiles_path), exist_ok=True)
        try:
            with open(self.profiles_path, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SpeakerVerifier Save Error]: {e}", flush=True)

    def is_enrolled(self) -> bool:
        return bool(self.profiles.get("owner"))

    def get_owner_name(self) -> str:
        owner = self.profiles.get("owner")
        return owner["name"] if owner else "друг"

    def get_users_list(self) -> list:
        users = []
        if self.profiles.get("owner"):
            users.append({"name": self.profiles["owner"]["name"], "is_owner": True})
        for uname in self.profiles.get("users", {}):
            users.append({"name": uname, "is_owner": False})
        return users

    def _prep_audio(self, audio_data):
        if isinstance(audio_data, bytes):
            samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        elif isinstance(audio_data, np.ndarray):
            if audio_data.dtype == np.int16:
                samples = audio_data.astype(np.float32) / 32768.0
            else:
                samples = audio_data.astype(np.float32)
        else:
            return None

        if len(samples) < 5000:
            return None

        rms = np.sqrt(np.mean(samples ** 2))
        if rms < 0.005:
            return None

        return samples

    def extract_embedding(self, audio_data) -> np.ndarray:
        if self.session is None:
            return None

        samples = self._prep_audio(audio_data)
        if samples is None:
            return None

        try:
            if len(self.input_shape) == 2:
                tensor_input = samples[np.newaxis, :]
            else:
                fbank = _extract_fbank(samples)
                if self.input_shape[1] == 80:
                    tensor_input = fbank.T[np.newaxis, :, :]
                else:
                    tensor_input = fbank[np.newaxis, :, :]

            outputs = self.session.run(None, {self.input_name: tensor_input})
            emb = np.array(outputs[0]).squeeze()

            norm = np.linalg.norm(emb)
            if norm > 1e-6:
                emb = emb / norm
            return emb
        except Exception as e:
            print(f"[SpeakerVerifier Extract Error]: {e}", flush=True)
            return None

    def start_enrollment(self):
        self.temp_enrollment_samples = []

    def add_enrollment_sample(self, audio_data) -> tuple[bool, int]:
        emb = self.extract_embedding(audio_data)
        if emb is not None:
            self.temp_enrollment_samples.append(emb)
            return True, len(self.temp_enrollment_samples)
        return False, len(self.temp_enrollment_samples)

    def commit_enrollment(self, user_name: str, is_owner: bool = False) -> bool:
        if not self.temp_enrollment_samples:
            return False

        avg_emb = np.mean(self.temp_enrollment_samples, axis=0)
        norm = np.linalg.norm(avg_emb)
        if norm > 1e-6:
            avg_emb = avg_emb / norm

        profile_data = {
            "name": user_name.strip(),
            "samples_count": len(self.temp_enrollment_samples),
            "embedding": avg_emb.tolist()
        }

        if is_owner:
            self.profiles["owner"] = profile_data
        else:
            if "users" not in self.profiles:
                self.profiles["users"] = {}
            self.profiles["users"][user_name.strip()] = profile_data

        self._save_profiles()
        self.temp_enrollment_samples = []
        return True

    def delete_user(self, user_name: str) -> bool:
        if self.profiles.get("owner") and self.profiles["owner"]["name"] == user_name:
            self.profiles["owner"] = None
            self._save_profiles()
            return True
        elif user_name in self.profiles.get("users", {}):
            del self.profiles["users"][user_name]
            self._save_profiles()
            return True
        return False

    def verify(self, audio_data) -> tuple[bool, str, float, bool]:
        if not self.is_enrolled():
            return True, "друг", 1.0, True

        cur_emb = self.extract_embedding(audio_data)
        if cur_emb is None:
            return False, "Неизвестный", 0.0, False

        best_score = -1.0
        best_name = "Неизвестный"
        is_owner = False

        owner = self.profiles.get("owner")
        if owner and "embedding" in owner:
            owner_emb = np.array(owner["embedding"], dtype=np.float32)
            score = float(np.dot(cur_emb, owner_emb))
            if score > best_score:
                best_score = score
                best_name = owner["name"]
                is_owner = True

        for uname, udata in self.profiles.get("users", {}).items():
            if "embedding" in udata:
                u_emb = np.array(udata["embedding"], dtype=np.float32)
                score = float(np.dot(cur_emb, u_emb))
                if score > best_score:
                    best_score = score
                    best_name = uname
                    is_owner = False

        is_recognized = best_score >= self.threshold
        return is_recognized, best_name, best_score, (is_owner if is_recognized else False)