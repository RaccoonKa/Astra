import os
import math
import time
import random
import atexit
import warnings
import threading
import numpy as np
import psutil
from services.telegram.telegram_bot import TelegramBotThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFrame, QFileDialog, QGridLayout,
    QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QPoint, QRectF, QTimer, QPropertyAnimation, QVariantAnimation,
    QEasingCurve, QParallelAnimationGroup, QThread, pyqtSignal, QEvent,
    QSize
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QRadialGradient,
    QBrush, QPainterPath, QFont, QFontDatabase, QGuiApplication,
    QIcon
)
from gui.styles import MAIN_STYLE
from gui.settings_window import SettingsFrame
from audio.stt import STTThread
from audio.tts import TTSThread
from core.nlp.command_parser import CommandParser
from core.system.actions import SystemActions
from core.vision.vision_provider import VisionThread
from core.vision.presence_manager import PresenceManager
from core.utils.config import get_resource_path, load_config, save_config
from core.utils.updater import UpdateCheckerThread
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from comtypes import CoInitialize, CoUninitialize
from core.system.volume_ducker import volume_ducker

warnings.filterwarnings("ignore", message="data discontinuity in recording")


class AudioVisualizerWorker(QThread):
    audio_data_signal = pyqtSignal(float, float, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.peak_level = 0.02

    def run(self):
        try:
            CoInitialize()
        except Exception:
            pass

        import soundcard as sc
        warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)

        while self.running:
            try:
                default_speaker = sc.default_speaker()
                if not default_speaker:
                    self.msleep(300)
                    continue

                mic = None
                try:
                    mic = sc.get_microphone(default_speaker.id, include_loopback=True)
                except Exception:
                    mic = None

                if not mic:
                    loopbacks = [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]
                    if loopbacks:
                        matching = [m for m in loopbacks if default_speaker.name in m.name or default_speaker.id == m.id]
                        mic = matching[0] if matching else loopbacks[0]

                if not mic:
                    self.msleep(300)
                    continue

                try:
                    recorder_ctx = mic.recorder(samplerate=None, blocksize=2048)
                except Exception:
                    recorder_ctx = mic.recorder(samplerate=44100, blocksize=2048)

                with recorder_ctx as recorder:
                    while self.running:
                        data = recorder.record(numframes=2048)
                        if not self.running:
                            break

                        samples = data[:, 0] if data.ndim > 1 else data
                        rms = float(np.sqrt(np.mean(samples ** 2)))

                        if rms < 0.002:
                            self.audio_data_signal.emit(0.0, 45.0, False)
                            continue

                        fft_vals = np.abs(np.fft.rfft(samples))
                        bass = float(np.sum(fft_vals[1:15]))

                        raw = rms * 2.2 + bass * 0.0045
                        self.peak_level = max(raw, self.peak_level * 0.985, 0.02)

                        normalized = min(1.0, (raw / self.peak_level) ** 1.35)
                        self.audio_data_signal.emit(normalized, 45.0, True)

            except Exception as e:
                print(f"[Audio Visualizer Error]: {e}")
                self.msleep(300)

        try:
            CoUninitialize()
        except Exception:
            pass

    def stop(self):
        self.running = False
        if self.isRunning():
            self.wait(200)


class CommandWorker(QThread):
    result_ready = pyqtSignal(object)

    def __init__(self, parser, text, audio_data=None, is_voice=False, attached_file=None, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.text = text
        self.audio_data = audio_data
        self.is_voice = is_voice
        self.attached_file = attached_file

    def run(self):
        response = self.parser.process_command(
            self.text,
            audio_data=self.audio_data,
            is_voice=self.is_voice,
            attached_file=self.attached_file
        )
        self.result_ready.emit(response)


class AstraMicWidget(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMouseTracking(True)
        self.is_processing = False
        self.music_blend = 0.0

        self.target_fps = 60
        self.speed_mult = 1.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

        self.pulse = 0.0
        self.boost = 0.0
        self.is_listening = False
        self.is_speaking = False

        self.beat_impulse = 0.0
        self.target_impulse = 0.0
        self.music_hue = 45.0

        self.emotion_palette = {
            "happy": (45.0, 230.0, 255.0),
            "sad": (198.0, 220.0, 255.0),
            "angry": (350.0, 235.0, 255.0),
            "surprise": (280.0, 220.0, 255.0),
            "neutral": (42.0, 45.0, 250.0),
            "other": (280.0, 220.0, 255.0)
        }

        self.target_emotion = "neutral"
        self.current_color_hue, self.current_color_sat, self.current_color_val = self.emotion_palette["neutral"]

        self.reset_emotion_timer = QTimer(self)
        self.reset_emotion_timer.setSingleShot(True)
        self.reset_emotion_timer.timeout.connect(self._reset_to_neutral)

        self.intro_progress = 0.0
        self.particles = []
        self.total_particles = 350
        self._init_particles()

    def set_framerate(self, fps: int):
        self.target_fps = fps
        self.speed_mult = 60.0 / fps
        interval = max(1, int(1000 / fps))
        self.timer.setInterval(interval)

    def _init_particles(self):
        self.particles.clear()
        for i in range(self.total_particles):
            r_dist = random.gauss(72, 14)
            if r_dist < 36:
                r_dist = 36 + random.uniform(0, 8)

            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(0.0015, 0.005) * (1 if random.random() > 0.2 else -0.6)

            x_start = -random.uniform(40, 160)
            y_start_off = random.gauss(0, 45)

            p1_x_off = -random.uniform(40, 100)
            p1_y_off = -random.uniform(30, 80)
            p2_x_off = random.uniform(30, 70)
            p2_y_off = random.uniform(20, 50)

            delay = (i / self.total_particles) * 0.55 + random.uniform(0, 0.04)

            self.particles.append({
                'r': r_dist,
                'accum_angle': angle,
                'speed': speed,
                'x_start': x_start,
                'y_start_off': y_start_off,
                'p1_x_off': p1_x_off,
                'p1_y_off': p1_y_off,
                'p2_x_off': p2_x_off,
                'p2_y_off': p2_y_off,
                'delay': delay,
                'size': random.uniform(0.6, 2.0),
                'alpha': random.randint(130, 255)
            })

    def start_intro_animation(self, duration=3800):
        self.intro_anim = QVariantAnimation(self)
        self.intro_anim.setDuration(duration)
        self.intro_anim.setStartValue(0.0)
        self.intro_anim.setEndValue(1.0)
        self.intro_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        def _on_val(v):
            self.intro_progress = float(v)
            self.update()

        self.intro_anim.valueChanged.connect(_on_val)
        self.intro_anim.start()

    def set_listening(self, state: bool):
        self.is_listening = state

    def set_processing(self, state: bool):
        self.is_processing = state
        if state:
            self.target_impulse = 0.0

    def set_speaking(self, state: bool):
        self.is_speaking = state

    def set_emotion(self, emotion: str):
        self.target_emotion = emotion if emotion in self.emotion_palette else "neutral"
        self.reset_emotion_timer.stop()
        if self.target_emotion != "neutral":
            self.reset_emotion_timer.start(12000)

    def _reset_to_neutral(self):
        self.target_emotion = "neutral"

    def trigger_wake_effect(self):
        self.boost = 4.5
        self.target_impulse = 0.8

    def on_audio_data(self, impulse: float, hue: float, is_music: bool):
        if self.is_speaking or self.is_listening or self.is_processing:
            self.target_impulse = 0.0
            return

        if is_music:
            scaled_impulse = impulse * self.music_blend
            if scaled_impulse > self.target_impulse:
                self.target_impulse = scaled_impulse
            self.music_hue = hue
        else:
            self.target_impulse = 0.0

    def animate(self):
        self.pulse += 0.015 * self.speed_mult
        self.beat_impulse += (self.target_impulse - self.beat_impulse) * 0.05 * self.speed_mult
        self.target_impulse *= math.pow(0.93, self.speed_mult)

        if self.is_listening:
            target_boost = 3.2
            self.music_blend = 0.0
        elif self.is_processing:
            target_boost = 2.0
            self.music_blend = 0.0
        elif self.is_speaking:
            target_boost = 1.3 + math.sin(self.pulse * 4.0) * 0.6
            self.music_blend = 0.0
        else:
            target_boost = 0.0
            self.music_blend = min(1.0, self.music_blend + 0.012 * self.speed_mult)

        self.boost += (target_boost - self.boost) * 0.08 * self.speed_mult
        effective_boost = self.boost if (self.is_listening or self.is_processing) else max(self.boost, self.beat_impulse * 2.8)

        if self.target_emotion != "neutral":
            target_h, target_s, target_v = self.emotion_palette[self.target_emotion]
        elif self.is_listening:
            target_h, target_s, target_v = (45.0, 150.0, 255.0)
        elif self.is_processing:
            target_h, target_s, target_v = (42.0, 80.0, 255.0)
        elif self.beat_impulse > 0.01 and self.music_blend > 0.15:
            target_h, target_s, target_v = (self.music_hue, 140.0, 240.0)
        else:
            target_h, target_s, target_v = self.emotion_palette["neutral"]

        color_rate = 0.06 * self.speed_mult
        self.current_color_hue += (target_h - self.current_color_hue) * color_rate
        self.current_color_sat += (target_s - self.current_color_sat) * color_rate
        self.current_color_val += (target_v - self.current_color_val) * color_rate

        for p in self.particles:
            p['accum_angle'] = (p['accum_angle'] + p['speed'] * (1.0 + effective_boost) * self.speed_mult) % (
                        math.pi * 2)

        self.update()

    def _get_bezier_pt(self, p0, p1, p2, p3, t):
        u = 1.0 - t
        tt = t * t
        uu = u * u
        return (
            uu * u * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + tt * t * p3[0],
            uu * u * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + tt * t * p3[1]
        )

    def paintEvent(self, event):
        T = self.intro_progress
        if T <= 0.001:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2

        p_val = math.sin(self.pulse * (2.5 if self.is_speaking else 1.0)) * (2.2 if self.is_speaking else 1.2)
        active_impulse = self.beat_impulse

        void_T = max(0.0, (T - 0.35) / 0.65)
        eased_void = void_T * void_T * (3.0 - 2.0 * void_T)

        speak_void = (abs(math.sin(self.pulse * 3.5)) * 9.0) if self.is_speaking else 0.0
        void_radius = (42 + (active_impulse * 20.0) + speak_void) * eased_void

        if void_radius > 1.0:
            void_shadow = QRadialGradient(cx, cy, void_radius)
            void_shadow.setColorAt(0.0, QColor(0, 0, 0, int(255 * eased_void)))
            void_shadow.setColorAt(0.85, QColor(0, 0, 0, int(255 * eased_void)))
            void_shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(void_shadow))
            painter.drawEllipse(QRectF(cx - void_radius, cy - void_radius, void_radius * 2, void_radius * 2))

        base_col = QColor.fromHsv(
            int(self.current_color_hue) % 360,
            int(max(0, min(255, self.current_color_sat))),
            int(max(0, min(255, self.current_color_val)))
        )

        painter.setPen(Qt.PenStyle.NoPen)

        for p in self.particles:
            if T < p['delay']:
                continue

            local_t = min(1.0, (T - p['delay']) / (1.0 - p['delay']))
            u = math.sin(local_t * (math.pi / 2))

            cur_angle = p['accum_angle']
            rad_focus = -14.0 if (self.is_listening or self.is_processing) else 0.0
            target_rad = p['r'] + rad_focus + (p_val * (1 if p['size'] > 1.2 else -1)) + (active_impulse * 24.0)
            target_x = cx + math.cos(cur_angle) * target_rad
            target_y = cy + math.sin(cur_angle) * target_rad

            if u < 1.0:
                p0 = (p['x_start'], cy + p['y_start_off'])
                p1 = (cx + p['p1_x_off'], cy + p['p1_y_off'])
                p2 = (cx + p['p2_x_off'], cy + p['p2_y_off'])
                p3 = (target_x, target_y)
                px, py = self._get_bezier_pt(p0, p1, p2, p3, u)
            else:
                px, py = target_x, target_y

            col = QColor(base_col)
            base_alpha = p['alpha'] * (0.85 if self.boost < 0.6 and active_impulse < 0.01 else 1.0)
            alpha = int(base_alpha * min(1.0, local_t * 1.8))
            col.setAlpha(alpha)

            painter.setBrush(QBrush(col))
            sz = p['size'] + (active_impulse * 1.8)
            painter.drawEllipse(QRectF(px - sz / 2, py - sz / 2, sz, sz))

    def mouseMoveEvent(self, event):
        if self.intro_progress < 0.95:
            self.unsetCursor()
            super().mouseMoveEvent(event)
            return

        cx, cy = self.width() / 2, self.height() / 2
        dist = math.hypot(event.pos().x() - cx, event.pos().y() - cy)
        if dist <= 95:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if self.intro_progress < 0.95:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            cx, cy = self.width() / 2, self.height() / 2
            dist = math.hypot(event.pos().x() - cx, event.pos().y() - cy)
            if dist <= 95:
                self.clicked.emit()
                event.accept()
                return
        super().mousePressEvent(event)

class AstraMiniMicWidget(AstraMicWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.total_particles = 100
        self._init_particles()

    def _init_particles(self):
        self.particles.clear()
        for i in range(self.total_particles):
            r_dist = random.gauss(14, 3)
            if r_dist < 8:
                r_dist = 8 + random.uniform(0, 3)

            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(0.0015, 0.005) * (1 if random.random() > 0.2 else -0.6)

            x_start = -random.uniform(5, 20)
            y_start_off = random.gauss(0, 10)

            p1_x_off = -random.uniform(10, 25)
            p1_y_off = -random.uniform(8, 20)
            p2_x_off = random.uniform(8, 18)
            p2_y_off = random.uniform(5, 12)

            delay = (i / self.total_particles) * 0.55 + random.uniform(0, 0.04)

            self.particles.append({
                'r': r_dist,
                'accum_angle': angle,
                'speed': speed,
                'x_start': x_start,
                'y_start_off': y_start_off,
                'p1_x_off': p1_x_off,
                'p1_y_off': p1_y_off,
                'p2_x_off': p2_x_off,
                'p2_y_off': p2_y_off,
                'delay': delay,
                'size': random.uniform(0.5, 1.2),
                'alpha': random.randint(130, 255)
            })

    def paintEvent(self, event):
        T = self.intro_progress
        if T <= 0.001:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = (self.height() / 2) - 12.0

        p_val = math.sin(self.pulse * (2.5 if self.is_speaking else 1.0)) * (0.8 if self.is_speaking else 0.4)
        active_impulse = self.beat_impulse

        void_T = max(0.0, (T - 0.35) / 0.65)
        eased_void = void_T * void_T * (3.0 - 2.0 * void_T)

        speak_void = (abs(math.sin(self.pulse * 3.5)) * 3.0) if self.is_speaking else 0.0
        void_radius = (9 + (active_impulse * 5.0) + speak_void) * eased_void

        if void_radius > 1.0:
            void_shadow = QRadialGradient(cx, cy, void_radius)
            void_shadow.setColorAt(0.0, QColor(0, 0, 0, int(255 * eased_void)))
            void_shadow.setColorAt(0.85, QColor(0, 0, 0, int(255 * eased_void)))
            void_shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(void_shadow))
            painter.drawEllipse(QRectF(cx - void_radius, cy - void_radius, void_radius * 2, void_radius * 2))

        base_col = QColor.fromHsv(
            int(self.current_color_hue) % 360,
            int(max(0, min(255, self.current_color_sat))),
            int(max(0, min(255, self.current_color_val)))
        )

        painter.setPen(Qt.PenStyle.NoPen)

        for p in self.particles:
            if T < p['delay']:
                continue

            local_t = min(1.0, (T - p['delay']) / (1.0 - p['delay']))
            u = math.sin(local_t * (math.pi / 2))

            cur_angle = p['accum_angle']
            rad_focus = -3.5 if (self.is_listening or getattr(self, 'is_processing', False)) else 0.0
            target_rad = p['r'] + rad_focus + p_val + (active_impulse * 6.0)
            target_x = cx + math.cos(cur_angle) * target_rad
            target_y = cy + math.sin(cur_angle) * target_rad

            if u < 1.0:
                p0 = (p['x_start'], cy + p['y_start_off'])
                p1 = (cx + p['p1_x_off'], cy + p['p1_y_off'])
                p2 = (cx + p['p2_x_off'], cy + p['p2_y_off'])
                p3 = (target_x, target_y)
                px, py = self._get_bezier_pt(p0, p1, p2, p3, u)
            else:
                px, py = target_x, target_y

            col = QColor(base_col)
            base_alpha = p['alpha'] * (0.85 if self.boost < 0.6 and active_impulse < 0.01 else 1.0)
            alpha = int(base_alpha * min(1.0, local_t * 1.8))
            col.setAlpha(alpha)

            painter.setBrush(QBrush(col))
            sz = p['size'] + (active_impulse * 0.8)
            painter.drawEllipse(QRectF(px - sz / 2, py - sz / 2, sz, sz))

class ChatFrame(QFrame):
    fade_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.border_phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_border)

        self.content_widget = QWidget(self)
        self.content_widget.setFixedHeight(280)
        self.content_widget.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self.content_widget)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        self.chat_history = QTextEdit()
        self.chat_history.setObjectName("ChatHistory")
        self.chat_history.setReadOnly(True)
        layout.addWidget(self.chat_history, 1)

        self.attached_file = None

        self.file_container = QWidget()
        file_layout = QHBoxLayout(self.file_container)
        file_layout.setContentsMargins(0, 0, 0, 4)
        file_layout.setSpacing(6)

        self.file_label = QLabel("")
        self.file_label.setObjectName("FileLabel")
        file_layout.addWidget(self.file_label)

        self.remove_file_btn = QPushButton("✕")
        self.remove_file_btn.setObjectName("RemoveFileBtn")
        self.remove_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_file_btn.setFixedSize(16, 16)
        self.remove_file_btn.clicked.connect(self.clear_attachment)
        file_layout.addWidget(self.remove_file_btn)
        file_layout.addStretch()

        self.file_container.hide()
        layout.addWidget(self.file_container, 0)

        self.input_container = QWidget()
        self.input_container.setObjectName("InputContainer")
        self.input_container.setStyleSheet("background: transparent;")
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.attach_button = QPushButton("📎")
        self.attach_button.setObjectName("AttachBtn")
        self.attach_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_button.setFixedSize(32, 32)
        self.attach_button.clicked.connect(self.select_file)
        input_layout.addWidget(self.attach_button)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("InputField")
        self.input_field.setFixedHeight(35)
        self.input_field.setPlaceholderText("Введите команду...")
        input_layout.addWidget(self.input_field, 1)

        self.send_button = QPushButton()
        self.send_button.setObjectName("AttachBtn")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setFixedSize(32, 32)
        icon_path = get_resource_path("assets", "img", "send_icon.png")
        self.send_button.setIcon(QIcon(icon_path))
        self.send_button.setIconSize(QSize(18, 18))
        input_layout.addWidget(self.send_button)

        layout.addWidget(self.input_container, 0)

        self.fade_overlay = QWidget(self.content_widget)
        self.fade_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.fade_overlay.setStyleSheet("background-color: rgba(8, 8, 5, 255); border-radius: 12px;")
        self.fade_overlay.hide()

        self.fade_anim = QVariantAnimation(self)
        self.fade_anim.setDuration(250)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.fade_anim.valueChanged.connect(self._update_overlay_alpha)
        self.fade_anim.finished.connect(self._on_fade_finished)
        self._is_fading_in = False

    def prepare_for_open(self):
        self.fade_overlay.setStyleSheet("background-color: rgba(8, 8, 5, 255); border-radius: 12px;")
        self.fade_overlay.show()
        self.fade_overlay.raise_()

    def fade_in(self):
        self.fade_overlay.raise_()
        self.fade_overlay.show()
        self._is_fading_in = True
        self.fade_anim.stop()
        self.fade_anim.setStartValue(255.0)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.start()

    def fade_out(self):
        self.fade_overlay.raise_()
        self.fade_overlay.show()
        self._is_fading_in = False
        self.fade_anim.stop()
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(255.0)
        self.fade_anim.start()

    def _update_overlay_alpha(self, alpha):
        self.fade_overlay.setStyleSheet(f"background-color: rgba(8, 8, 5, {int(alpha)}); border-radius: 12px;")

    def _on_fade_finished(self):
        if self._is_fading_in:
            self.fade_overlay.hide()
        self.fade_finished.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        self.content_widget.setGeometry(0, h - 280, w, 280)
        self.fade_overlay.setGeometry(0, 0, w, 280)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'timer') and not self.timer.isActive():
            self.timer.start(35)

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()

    def mousePressEvent(self, event):
        event.accept()

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл для Астры",
            "",
            "Все поддерживаемые файлы (*.txt *.pdf *.docx *.png *.jpg *.jpeg *.bmp *.webp *.md *.py *.json *.csv *.log);;Изображения (*.png *.jpg *.jpeg *.bmp *.webp);;Тексты и Документы (*.txt *.pdf *.docx *.md *.py *.json *.csv *.log)"
        )
        if path:
            self.attached_file = path
            self.file_label.setText(f"📎 {os.path.basename(path)}")
            self.file_container.show()

    def clear_attachment(self):
        self.attached_file = None
        self.file_label.clear()
        self.file_container.hide()

    def animate_border(self):
        self.border_phase += 0.010
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w < 20 or h < 20:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.75, 0.75, w - 1.5, h - 1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        painter.fillPath(path, QColor(8, 8, 5, 240))

        cx, cy = w / 2, h / 2
        dx = math.cos(self.border_phase) * w
        dy = math.sin(self.border_phase) * h

        border_grad = QLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
        border_grad.setColorAt(0.0, QColor("#181406"))
        border_grad.setColorAt(0.35, QColor("#3a3010"))
        border_grad.setColorAt(0.5, QColor("#5c4e1a"))
        border_grad.setColorAt(0.65, QColor("#3a3010"))
        border_grad.setColorAt(1.0, QColor("#181406"))

        pen_border = QPen(QBrush(border_grad), 1.5)
        painter.setPen(pen_border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class BackgroundFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.wave_phase = 0.0
        self.speed_mult = 1.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_bg)
        self.timer.start(16)

        self.stars = []
        for _ in range(70):
            self.stars.append({
                'rx': random.uniform(0.01, 0.99),
                'ry': random.uniform(0.01, 0.99),
                'size': random.uniform(0.5, 1.2),
                'phase': random.uniform(0, math.pi * 2),
                'speed': random.uniform(0.015, 0.035)
            })

        self.dust_cloud = []
        gold_spectrum = ["#ffffff", "#fffde7", "#fff59d", "#ffee55", "#ffd700", "#e5c158", "#c4a028", "#997a1e"]
        for _ in range(900):
            curve = random.choice([0, 0, 0, 1, 1, 2])
            spread = random.gauss(0, 12) if random.random() < 0.7 else random.gauss(0, 26)
            self.dust_cloud.append({
                'curve_idx': curve,
                't': random.uniform(0.0, 1.0),
                'offset_x': random.gauss(0, 14),
                'offset_y': spread,
                'size': random.uniform(0.6, 1.6),
                'color': random.choice(gold_spectrum),
                'alpha': random.randint(40, 230),
                'twinkle_speed': random.uniform(0.02, 0.06),
                'twinkle_phase': random.uniform(0, math.pi * 2)
            })

    def set_framerate(self, fps: int):
        self.speed_mult = 60.0 / fps
        interval = max(1, int(1000 / fps))
        self.timer.setInterval(interval)

    def animate_bg(self):
        self.wave_phase += 0.005 * self.speed_mult
        for star in self.stars:
            star['phase'] += star['speed'] * self.speed_mult
        for d in self.dust_cloud:
            d['twinkle_phase'] += d['twinkle_speed'] * self.speed_mult
        self.update()

    def _get_bezier_point(self, p0, p1, p2, p3, t):
        u = 1 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t
        x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        return x, y

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)

        painter.fillPath(clip_path, QColor("#000000"))
        painter.setClipPath(clip_path)

        for star in self.stars:
            sx = star['rx'] * w
            sy = star['ry'] * h
            twinkle = (math.sin(star['phase']) + 1) / 2
            alpha = int(20 + twinkle * 210)
            sz = star['size']

            col = QColor(255, 255, 255, alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col))
            painter.drawEllipse(QRectF(sx - sz, sy - sz, sz * 2, sz * 2))

        shift1 = math.sin(self.wave_phase) * 20
        shift2 = math.cos(self.wave_phase * 0.6) * 24

        curves = [
            ((w * 0.02, h + 80), (w * 0.35 + shift1, h * 0.42 + shift2), (w * 0.68 - shift2, h * 0.82 + shift1),
             (w + 80, h * 0.18)),
            ((w * 0.15, h + 80), (w * 0.48 - shift2, h * 0.52 + shift1), (w * 0.78 + shift1, h * 0.78 - shift2),
             (w + 80, h * 0.42)),
            ((w * 0.32, h + 80), (w * 0.62 + shift1, h * 0.65 - shift2), (w * 0.88 - shift1, h * 0.86 + shift2),
             (w + 80, h * 0.68))
        ]

        for d in self.dust_cloud:
            p0, p1, p2, p3 = curves[d['curve_idx']]
            bx, by = self._get_bezier_point(p0, p1, p2, p3, d['t'])
            px = bx + d['offset_x']
            py = by + d['offset_y']

            twinkle = (math.sin(d['twinkle_phase']) + 1) / 2
            alpha = int(d['alpha'] * (0.5 + 0.5 * twinkle))

            col = QColor(d['color'])
            col.setAlpha(alpha)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col))
            sz = d['size']
            painter.drawEllipse(QRectF(px - sz / 2, py - sz / 2, sz, sz))

        pen_border = QPen(QColor("#111111"), 1.5)
        painter.setPen(pen_border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), 16, 16)


class VolumeDucker:
    def __init__(self):
        self.saved_volumes = {}

    def _duck_async(self):
        try:
            CoInitialize()
            self.saved_volumes.clear()
            sessions = AudioUtilities.GetAllSessions()
            current_pid = os.getpid()

            for session in sessions:
                process = session.Process
                if process:
                    name = process.name().lower()
                    if process.pid == current_pid or "astra" in name or "python" in name or "pycharm" in name:
                        continue

                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                    current_vol = volume.GetMasterVolume()
                    self.saved_volumes[process.pid] = current_vol

                    volume.SetMasterVolume(current_vol * 0.10, None)
        except Exception as e:
            print(f"[Volume Ducker Error]: {e}")
        finally:
            try:
                CoUninitialize()
            except Exception:
                pass

    def duck(self):
        threading.Thread(target=self._duck_async, daemon=True).start()

    def _restore_async(self):
        if not self.saved_volumes:
            return

        try:
            CoInitialize()
            sessions = AudioUtilities.GetAllSessions()

            for session in sessions:
                process = session.Process
                if process and process.pid in self.saved_volumes:
                    try:
                        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                        saved_vol = self.saved_volumes[process.pid]
                        volume.SetMasterVolume(saved_vol, None)
                    except Exception:
                        pass

            self.saved_volumes.clear()
        except Exception as e:
            print(f"[Volume Ducker Error]: {e}")
        finally:
            try:
                CoUninitialize()
            except Exception:
                pass

    def restore(self):
        threading.Thread(target=self._restore_async, daemon=True).start()


class MainWindow(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.drag_position = QPoint()
        self.ui_revealed = False
        self.command_parser = CommandParser()

        mgr = self.command_parser.reminder_manager
        mgr.timer_fired.connect(self._on_timer_fired)
        mgr.alarm_fired.connect(self._on_alarm_fired)
        mgr.reminder_fired.connect(self._on_reminder_fired)
        mgr.missed_reminders_signal.connect(self._on_missed_reminders)

        self.is_mini_mode = False

        self.vision_thread = None
        self.presence_manager = None

        self.is_muted = self.config.get("is_muted", False) if isinstance(self.config, dict) else False
        self.is_mini_mode = self.config.get("is_mini_mode", False) if isinstance(self.config, dict) else False
        self.is_whisper_mode = self.config.get("is_whisper_mode", False) if isinstance(self.config, dict) else False

        self.absence_start_time = None
        self.warned_battery_50 = False
        self.warned_battery_25 = False
        self.warned_battery_tg_30 = False

        self.init_ui()
        self.init_audio()

        self.battery_timer = QTimer(self)
        self.battery_timer.timeout.connect(self.check_battery_status)
        self.battery_timer.start(45000)

        self.settings_panel.fps_changed.connect(self.apply_framerate)

        cfg_modules = self.config.get("modules", {}) if isinstance(self.config, dict) else {}
        if cfg_modules.get("vision", False):
            QTimer.singleShot(12500, self.start_vision)

        atexit.register(volume_ducker.force_restore)

        self.telegram_thread = None
        QTimer.singleShot(8500, self._start_telegram_delayed)

        QTimer.singleShot(3000, self._check_updates)

        initial_fps = self.config.get("target_fps", 60) if isinstance(self.config, dict) else 60
        self.apply_framerate(initial_fps)

    def _on_timer_fired(self, task):
        text = task.get("text", "Таймер")
        msg = f"Время вышло! {text} завершён ⏳"
        self.chat_history.append(f"Астра: {msg}\n")
        self.left_panel.set_emotion("surprise")
        self.mini_left_panel.set_emotion("surprise")

    def _on_alarm_fired(self, task):
        msg = "Будильник! Пора просыпаться ⏰ (Скажи 'Стоп' или 'Отложи')"
        self.chat_history.append(f"Астра: {msg}\n")
        self.speak_reply("Будильник! Пора просыпаться.")
        self.left_panel.set_emotion("happy")
        self.mini_left_panel.set_emotion("happy")

    def _on_reminder_fired(self, task):
        text = task.get("text", "")
        msg = f"Напоминаю: {text} 🔔"
        self.chat_history.append(f"Астра: {msg}\n")
        self.speak_reply(f"Напоминаю: {text}")
        self.left_panel.set_emotion("happy")
        self.mini_left_panel.set_emotion("happy")

    def _on_missed_reminders(self, missed_list):
        items_str = ", ".join(missed_list)
        msg = f"Пока ПК был выключен, наступило время: {items_str} 📌"
        self.chat_history.append(f"Астра: {msg}\n")

    def apply_framerate(self, fps: int):
        if hasattr(self, 'left_panel'):
            self.left_panel.set_framerate(fps)
        if hasattr(self, 'bg_frame'):
            self.bg_frame.set_framerate(fps)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if not getattr(self, '_is_animating_window', False):
                if self.windowState() == Qt.WindowState.WindowNoState and event.oldState() == Qt.WindowState.WindowMinimized:
                    self.show_animated()
        super().changeEvent(event)

    def show_animated(self):
        if hasattr(self, 'closing_anim') and self.closing_anim.state() == QPropertyAnimation.State.Running:
            self.closing_anim.stop()

        self._is_animating_window = True

        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()

        w = self.width()
        h = self.height()
        x = avail.x() + avail.width() - w - 20
        y = avail.y() + avail.height() - h - 20
        start_y = avail.y() + avail.height() + 50

        if not self.isVisible() or self.isMinimized():
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.move(x, start_y)
            super().showNormal()

        self.activateWindow()

        self.opening_anim = QPropertyAnimation(self, b"pos")
        self.opening_anim.setDuration(450)
        self.opening_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.opening_anim.setStartValue(QPoint(x, start_y))
        self.opening_anim.setEndValue(QPoint(x, y))

        def _on_opened():
            self._is_animating_window = False

        self.opening_anim.finished.connect(_on_opened)
        self.opening_anim.start()

    def _animate_down_and_do(self, action_func):
        if hasattr(self, 'closing_anim') and self.closing_anim.state() == QPropertyAnimation.State.Running:
            return

        if hasattr(self, 'opening_anim') and self.opening_anim.state() == QPropertyAnimation.State.Running:
            self.opening_anim.stop()

        self._is_animating_window = True
        avail = QGuiApplication.primaryScreen().availableGeometry()
        target_y = avail.y() + avail.height() + 50

        self.closing_anim = QPropertyAnimation(self, b"pos")
        self.closing_anim.setDuration(450)
        self.closing_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.closing_anim.setStartValue(self.pos())
        self.closing_anim.setEndValue(QPoint(self.x(), target_y))

        def _on_closed():
            self._is_animating_window = False
            action_func()

        self.closing_anim.finished.connect(_on_closed)
        self.closing_anim.start()

    def _animate_down_and_do(self, action_func):
        if hasattr(self, 'closing_anim') and self.closing_anim.state() == QPropertyAnimation.State.Running:
            return

        if hasattr(self, 'opening_anim') and self.opening_anim.state() == QPropertyAnimation.State.Running:
            self.opening_anim.stop()

        self._is_animating_window = True
        full = QGuiApplication.primaryScreen().geometry()
        target_y = full.y() + full.height() + 15

        self.closing_anim = QPropertyAnimation(self, b"pos")
        self.closing_anim.setDuration(450)
        self.closing_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.closing_anim.setStartValue(self.pos())
        self.closing_anim.setEndValue(QPoint(self.x(), target_y))

        def _on_closed():
            self._is_animating_window = False
            action_func()

        self.closing_anim.finished.connect(_on_closed)
        self.closing_anim.start()

    def minimize_animated(self):
        self._animate_down_and_do(self.showMinimized)

    def close_animated(self):
        self._animate_down_and_do(self.hide)

    def show(self):
        self.show_animated()

    def showNormal(self):
        self.show_animated()

    def _start_telegram_delayed(self):
        if self.telegram_thread is None:
            self.telegram_thread = TelegramBotThread(parent=self)
            self.telegram_thread.start()

    def _check_updates(self):
        self.update_checker = UpdateCheckerThread(parent=self)
        self.update_checker.update_available.connect(self.on_update_found)
        self.update_checker.start()

    def on_update_found(self, new_ver: str, changelog: str, download_url: str):
        self.settings_panel.set_update_available(new_ver, changelog, download_url)
        self.update_badge_btn.setText(f"✨ v{new_ver} доступна!")
        self.update_badge_btn.show()

    def open_settings_for_update(self):
        if not (self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0):
            self.toggle_settings()
        self.settings_panel.scroll_to_bottom()

    def toggle_mini_mode(self):
        self.is_mini_mode = not self.is_mini_mode
        pos = self.pos()

        self.hide()
        flags = self.windowFlags()

        if self.is_mini_mode:
            flags |= Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.right_area.hide()
            self.mini_mode_container.show()
            self.setFixedSize(450, 60)
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.mini_mode_container.hide()
            self.right_area.show()
            self.setFixedSize(380, 560)

        self.move(pos)
        self.show()

        cfg = load_config()
        cfg["is_mini_mode"] = self.is_mini_mode
        if isinstance(self.config, dict):
            self.config["is_mini_mode"] = self.is_mini_mode
        save_config(cfg)

    def send_mini_message(self):
        if not self.ui_revealed:
            return

        text = self.mini_input_field.text().strip()
        if text:
            self.chat_history.append(f"Вы: {text}")

            text_low = text.lower()
            if any(w in text_low for w in ["заблокируй", "залочь", "заблокировать", "залочить"]):
                self.absence_start_time = time.time()
                if self.presence_manager:
                    self.presence_manager.set_manual_absence(grace_period=10)

            self.mini_input_field.clear()
            self.mini_input_field.setEnabled(False)
            self.mini_send_button.setEnabled(False)

            self.mini_text_worker = CommandWorker(self.command_parser, text, is_voice=False, parent=self)
            self.mini_text_worker.result_ready.connect(self.on_mini_text_command_finished)
            self.mini_text_worker.start()

    def on_mini_text_command_finished(self, response):
        self.mini_input_field.setEnabled(True)
        self.mini_send_button.setEnabled(True)
        self.mini_input_field.setFocus()

        if response:
            if isinstance(response, dict):
                chat_text = response.get("chat", "") or response.get("voice", "")
                voice_text = response.get("voice", "")
                emotion = response.get("emotion", "neutral")
            else:
                chat_text = voice_text = str(response)
                emotion = getattr(self.command_parser, "last_emotion", "neutral")

            self.left_panel.set_emotion(emotion)
            self.mini_left_panel.set_emotion(emotion)

            if chat_text:
                self.chat_history.append(f"Астра: {chat_text}\n")
            if voice_text:
                self.speak_reply(voice_text, is_whisper=False)

    def init_ui(self):
        font_path = get_resource_path("assets", "fonts", "Schiffbauer-Regular.otf")
        font_id = QFontDatabase.addApplicationFont(font_path)

        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            self.font_family = families[0] if families else "Arial"
            self.custom_font = QFont(self.font_family, 11)
        else:
            self.font_family = "Arial"
            self.custom_font = QFont(self.font_family, 11)

        self.setFont(self.custom_font)

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(380, 560)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.bg_frame = BackgroundFrame()
        self.bg_frame.setObjectName("CentralWidget")
        self.bg_frame.setStyleSheet(MAIN_STYLE)

        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(6, 6, 6, 6)
        container_layout.setSpacing(0)

        self.right_area = QWidget()
        right_area_layout = QVBoxLayout()
        right_area_layout.setContentsMargins(0, 0, 0, 0)
        right_area_layout.setSpacing(0)

        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(10, 0, 10, 0)

        self.title_btns_widget = QWidget()
        title_btns_layout = QHBoxLayout(self.title_btns_widget)
        title_btns_layout.setContentsMargins(0, 0, 0, 0)
        title_btns_layout.setSpacing(6)

        self.update_badge_btn = QPushButton("✨ v3.0.0 доступна!")
        self.update_badge_btn.setObjectName("UpdateNotificationBadge")
        self.update_badge_btn.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        self.update_badge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_badge_btn.clicked.connect(self.open_settings_for_update)
        self.update_badge_btn.hide()
        title_btns_layout.addWidget(self.update_badge_btn)

        self.exit_btn = QPushButton("⏻")
        self.exit_btn.setObjectName("ExitBtn")
        self.exit_btn.setFixedWidth(30)
        self.exit_btn.setToolTip("Закрыть Астру")
        self.exit_btn.clicked.connect(self.exit_app)
        title_btns_layout.addWidget(self.exit_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("TitleBtn")
        self.settings_btn.setToolTip("Настройки")
        self.settings_btn.setFixedWidth(30)
        self.settings_btn.clicked.connect(self.toggle_settings)
        title_btns_layout.addWidget(self.settings_btn)

        self.mini_mode_btn = QPushButton("⛶")
        self.mini_mode_btn.setObjectName("TitleBtn")
        self.mini_mode_btn.setFixedWidth(30)
        self.mini_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_mode_btn.setToolTip("Мини-режим (поверх окон)")
        self.mini_mode_btn.setStyleSheet(
            "QPushButton { color: #ffffff; } QPushButton:hover { color: #ffd700; background-color: rgba(92, 78, 26, 0.2); }")
        self.mini_mode_btn.clicked.connect(self.toggle_mini_mode)
        title_btns_layout.addWidget(self.mini_mode_btn)

        self.toggle_chat_btn = QPushButton("💭")
        self.toggle_chat_btn.setObjectName("TitleBtn")
        self.toggle_chat_btn.setToolTip("Открыть чат")
        self.toggle_chat_btn.setFixedWidth(30)
        self.toggle_chat_btn.clicked.connect(self.toggle_chat)
        title_btns_layout.addWidget(self.toggle_chat_btn)

        self.mute_btn = QPushButton("🔇" if self.is_muted else "🔊")
        self.mute_btn.setObjectName("TitleBtn")
        self.mute_btn.setFixedWidth(30)
        self.mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mute_btn.setToolTip("Включить голос Астры!" if self.is_muted else "Выключить голос Астры!")
        self.mute_btn.clicked.connect(self.toggle_mute)
        title_btns_layout.addWidget(self.mute_btn)

        self.whisper_btn = QPushButton("🤫" if self.is_whisper_mode else "📢")
        self.whisper_btn.setObjectName("TitleBtn")
        self.whisper_btn.setFixedWidth(30)
        self.whisper_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.whisper_btn.setToolTip(
            "Выключить разговор шепотом" if self.is_whisper_mode else "Включить разговор только шепотом")
        self.whisper_btn.clicked.connect(self.toggle_whisper_mode)
        title_btns_layout.addWidget(self.whisper_btn)

        title_bar.addWidget(self.title_btns_widget)
        title_bar.addStretch()

        min_btn = QPushButton("—")
        min_btn.setObjectName("MinBtn")
        min_btn.setFixedWidth(30)
        min_btn.clicked.connect(self.minimize_animated)
        title_bar.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedWidth(30)
        close_btn.clicked.connect(self.close_animated)
        title_bar.addWidget(close_btn)

        right_area_layout.addLayout(title_bar)

        self.content_layout = QGridLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self.mic_chat_container = QWidget()
        mic_chat_layout = QVBoxLayout(self.mic_chat_container)
        mic_chat_layout.setContentsMargins(0, 0, 0, 0)
        mic_chat_layout.setSpacing(0)

        self.left_panel = AstraMicWidget(self)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(15, 0, 0, 12)
        left_layout.addStretch()

        mic_chat_layout.addWidget(self.left_panel)

        self.right_panel = ChatFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_panel.setMinimumHeight(0)
        self.right_panel.setMaximumHeight(0)
        self.right_panel.hide()
        mic_chat_layout.addWidget(self.right_panel)

        self.content_layout.addWidget(self.mic_chat_container, 0, 0)

        self.settings_panel = SettingsFrame()
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setFixedHeight(480)
        self.settings_panel.setMinimumWidth(0)
        self.settings_panel.setMaximumWidth(0)
        self.settings_panel.hide()
        self.settings_panel.speak_requested.connect(self.speak_reply)
        self.settings_panel.vision_state_changed.connect(self.on_vision_state_changed)
        self.settings_panel.fps_changed.connect(self.apply_framerate)

        self.content_layout.addWidget(self.settings_panel, 0, 0,
                                      Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)

        right_area_layout.addLayout(self.content_layout)
        self.right_area.setLayout(right_area_layout)
        container_layout.addWidget(self.right_area)

        self.chat_history = self.right_panel.chat_history
        self.chat_history.setFont(QFont(self.font_family, 12))
        self.input_field = self.right_panel.input_field
        self.input_field.setFont(QFont(self.font_family, 12))
        self.send_button = self.right_panel.send_button
        self.send_button.setFont(QFont(self.font_family, 12))

        self.input_field.returnPressed.connect(self.send_message)
        self.send_button.clicked.connect(self.send_message)

        self.bg_frame.setLayout(container_layout)
        main_layout.addWidget(self.bg_frame)
        self.setLayout(main_layout)

        self.title_btns_opacity = QGraphicsOpacityEffect(self.title_btns_widget)
        self.title_btns_opacity.setOpacity(0.0)
        self.title_btns_widget.setGraphicsEffect(self.title_btns_opacity)

        self.title_btns_anim = QPropertyAnimation(self.title_btns_opacity, b"opacity")
        self.title_btns_anim.setDuration(700)
        self.title_btns_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.title_btns_anim.setStartValue(0.0)
        self.title_btns_anim.setEndValue(1.0)

        self.title_btns_widget.hide()
        self.set_ui_interactive(False)

        self.settings_anim_group = QParallelAnimationGroup(self)
        self.chat_anim_group = QParallelAnimationGroup(self)

        self.settings_anim_group.finished.connect(self._on_settings_anim_finished)
        self._pending_action = None

        self.mini_mode_container = QWidget()
        self.mini_mode_container.hide()
        mini_layout = QHBoxLayout(self.mini_mode_container)
        mini_layout.setContentsMargins(10, 10, 10, 10)
        mini_layout.setSpacing(10)

        self.mini_exit_btn = QPushButton("⏻")
        self.mini_exit_btn.setObjectName("TitleBtn")
        self.mini_exit_btn.setFixedSize(30, 30)
        self.mini_exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_exit_btn.setStyleSheet(
            "QPushButton { color: #ffffff; } QPushButton:hover { color: #ffd700; background-color: rgba(92, 78, 26, 0.2); }"
        )
        self.mini_exit_btn.clicked.connect(self.exit_app)
        mini_layout.addWidget(self.mini_exit_btn)

        self.mini_restore_btn = QPushButton("⛶")
        self.mini_restore_btn.setObjectName("TitleBtn")
        self.mini_restore_btn.setFixedSize(30, 30)
        self.mini_restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_restore_btn.setToolTip("Вернуться в полный режим")
        self.mini_restore_btn.setStyleSheet(
            "QPushButton { color: #ffffff; } QPushButton:hover { color: #ffd700; background-color: rgba(92, 78, 26, 0.2); }")
        self.mini_restore_btn.clicked.connect(self.toggle_mini_mode)
        mini_layout.addWidget(self.mini_restore_btn)

        self.mini_left_panel = AstraMiniMicWidget(self)
        self.mini_left_panel.setFixedSize(60, 60)
        mini_layout.addWidget(self.mini_left_panel, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.mini_input_field = QLineEdit()
        self.mini_input_field.setObjectName("InputField")
        self.mini_input_field.setFixedHeight(35)
        self.mini_input_field.setPlaceholderText("Команда...")
        self.mini_input_field.setFont(QFont(self.font_family, 12))
        self.mini_input_field.returnPressed.connect(self.send_mini_message)
        mini_layout.addWidget(self.mini_input_field, 1)

        self.mini_send_button = QPushButton()
        self.mini_send_button.setObjectName("AttachBtn")
        self.mini_send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_send_button.setFixedSize(32, 32)
        icon_path = get_resource_path("assets", "img", "send_icon.png")
        self.mini_send_button.setIcon(QIcon(icon_path))
        self.mini_send_button.setIconSize(QSize(18, 18))
        self.mini_send_button.clicked.connect(self.send_mini_message)
        mini_layout.addWidget(self.mini_send_button)

        container_layout.addWidget(self.mini_mode_container)

        if self.is_mini_mode:
            self.right_area.setVisible(False)
            self.mini_mode_container.setVisible(True)
            self.setFixedSize(450, 60)
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.mini_mode_container.setVisible(False)
            self.right_area.setVisible(True)
            self.setFixedSize(380, 560)

    def check_battery_status(self):
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return

            if battery.power_plugged:
                self.warned_battery_50 = False
                self.warned_battery_25 = False
                self.warned_battery_tg_30 = False
                return

            percent = battery.percent

            if percent <= 30 and not getattr(self, 'warned_battery_tg_30', False):
                self.warned_battery_tg_30 = True
                from services.telegram.notifier import send_telegram_notification
                send_telegram_notification(
                    f"🔋 **Внимание!** Батарея ноутбука разрядилась до **{percent}%**! Подключи зарядное устройство, чтобы не потерять работу."
                )

            if percent <= 25 and not self.warned_battery_25:
                self.warned_battery_25 = True
                self.warned_battery_50 = True
                msg = "Осталось всего двадцать пять процентов заряда. Подключи ноутбук к розетке, чтобы он не выключился!"
                self.chat_history.append(f"Астра: {msg}\n")
                self.speak_reply(msg)
            elif percent <= 50 and not self.warned_battery_50:
                self.warned_battery_50 = True
                msg = "Батарея разрядилась до половины. Осталось пятьдесят процентов."
                self.chat_history.append(f"Астра: {msg}\n")
                self.speak_reply(msg)
            elif percent > 55:
                self.warned_battery_50 = False
                self.warned_battery_25 = False
                self.warned_battery_tg_30 = False
            elif percent > 35:
                self.warned_battery_tg_30 = False
            elif percent > 30:
                self.warned_battery_25 = False
        except Exception:
            pass

    def on_user_left(self):
        self.absence_start_time = time.time()
        SystemActions.lock_screen()

    def on_user_returned(self):
        cfg = load_config()
        user_name = cfg.get("user_name", "друг")

        elapsed = (time.time() - self.absence_start_time) if self.absence_start_time else 0
        self.absence_start_time = None

        if elapsed < 120:
            msg = random.choice([
                f"Ой, ты уже здесь! А я только плед поудобнее поправила. 🥰 Что делаем?",
                "Уже тут? Твоя суперспос+обность — решать дела за секунды! 😧",
                "Уже тут? Как я рада! А то без тебя здесь скучно. 🤗",
                f"Ты летаешь быстрее ветра, {user_name}! 😶‍🌫️ Я готова продолжать.",
                "А я только налила воображаемый чай... Ну ладно, продолжаем! 🥰",
                "Не можешь без меня долго? 😊💛",
                "А я только хотела устроить цифровую си+есту... ✨ Вся во внимании!"
            ])
        elif elapsed < 1800:
            msg = random.choice([
                "Две минуты — мало, тридцать — много, а сейчас — в самый раз! ☺️ Что на очереди?",
                f"Маленький перерыв — это полезно, {user_name}. Рада, что ты снова со мной! 😊",
                "Ты снова здесь! А я тут как раз считала облака за ок+ошком ☁️. Что делаем дальше?"
            ])
        elif elapsed < 7200:
            msg = random.choice([
                "О, знакомые всё лица! Вся во внимании! 🥰",
                "Рада видеть тебя в строю! Перерыв получился отличным, пора за дело. 😌",
                "Ура, ты снова здесь! Соскучиться я успела, но главное — ты снова на связи. 🤗💛"
            ])
        else:
            msg = random.choice([
                "Какая долгая разлука! Я очень сильно по тебе соскучилась. 🥺💛 Вся во внимании!",
                "Привет-привет! Время без тебя тянулось очень долго! 🥺💛",
                "Ого, целая вечность прошла! Я уже хотела писать тебе письмо в реальный мир. 😉💛",
                "Привет! Мой датчик радости сейчас зашкаливает. Больше так надолго не пропадай! 🥺💛"
            ])

        self.chat_history.append(f"Астра: {msg}\n")
        self.speak_reply(msg)

    def on_deep_drowsiness(self):
        cfg = load_config()
        if not cfg.get("modules", {}).get("eye_tracking", False):
            return

        user_name = cfg.get("user_name", "друг")
        msg = f"{user_name}, тебе нужно поспать! Не забывай о своём здоровье!"

        self.chat_history.append(f"Астра: {msg}\n")
        self.speak_reply(msg)

    def on_frequent_blinking(self):
        cfg = load_config()
        if not cfg.get("modules", {}).get("eye_tracking", False):
            return

        user_name = cfg.get("user_name", "друг")
        msg = f"{user_name}, сделай перерыв и отдохни!"

        self.chat_history.append(f"Астра: {msg}\n")
        self.speak_reply(msg)

    def set_ui_interactive(self, enabled: bool):
        self.exit_btn.setEnabled(enabled)
        self.settings_btn.setEnabled(enabled)
        self.toggle_chat_btn.setEnabled(enabled)
        if hasattr(self, 'mute_btn'):
            self.mute_btn.setEnabled(enabled)
        if hasattr(self, 'whisper_btn'):
            self.whisper_btn.setEnabled(enabled)
        if hasattr(self, 'mini_mode_btn'):
            self.mini_mode_btn.setEnabled(enabled)
        if hasattr(self, 'mini_exit_btn'):
            self.mini_exit_btn.setEnabled(enabled)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.mute_btn.setText("🔇")
            self.mute_btn.setToolTip("Включить голос Астры")
            if hasattr(self, 'tts_thread') and self.tts_thread.isRunning():
                self.tts_thread.stop()
            if hasattr(self, 'left_panel'):
                self.left_panel.set_speaking(False)
        else:
            self.mute_btn.setText("🔊")
            self.mute_btn.setToolTip("Выключить голос Астры!")

        cfg = load_config()
        cfg["is_muted"] = self.is_muted
        if isinstance(self.config, dict):
            self.config["is_muted"] = self.is_muted
        save_config(cfg)

    def toggle_whisper_mode(self):
        self.is_whisper_mode = not self.is_whisper_mode
        if self.is_whisper_mode:
            self.whisper_btn.setText("🤫")
            self.whisper_btn.setToolTip("Выключить разговор шепотом")
        else:
            self.whisper_btn.setText("📢")
            self.whisper_btn.setToolTip("Включить разговор только шепотом")

        cfg = load_config()
        cfg["is_whisper_mode"] = self.is_whisper_mode
        if isinstance(self.config, dict):
            self.config["is_whisper_mode"] = self.is_whisper_mode
        save_config(cfg)

    def exit_app(self):
        self.hide()
        volume_ducker.force_restore()
        os._exit(0)

    def init_audio(self):
        self.stt_thread = STTThread(parent=self)
        self.stt_thread.text_recognized.connect(self.on_speech_recognized)
        self.stt_thread.listening_state_changed.connect(self.left_panel.set_listening)
        self.stt_thread.listening_state_changed.connect(self.mini_left_panel.set_listening)
        self.stt_thread.error_occurred.connect(self.on_stt_error)
        self.stt_thread.start()

        self.pending_followup = False
        self.stt_thread.wake_word_detected.connect(self.on_wake_word_detected)

        self.tts_thread = TTSThread(parent=self)
        self.tts_thread.warmup_finished.connect(self.on_warmup_completed)
        self.tts_thread.speaking_finished.connect(self.on_tts_finished)

        self.tts_thread.speaking_started.connect(lambda: volume_ducker.duck(factor=0.05))
        self.tts_thread.speaking_finished.connect(volume_ducker.restore)

        self.tts_thread.speaking_started.connect(lambda: self.mini_left_panel.set_speaking(True))
        self.tts_thread.speaking_finished.connect(lambda: self.mini_left_panel.set_speaking(False))
        self.mini_left_panel.clicked.connect(self.stt_thread.trigger_manual_listen)

        self.left_panel.clicked.connect(self.stt_thread.trigger_manual_listen)

        self.audio_worker = AudioVisualizerWorker(parent=self)
        self.audio_worker.audio_data_signal.connect(self.left_panel.on_audio_data)
        self.audio_worker.audio_data_signal.connect(self.mini_left_panel.on_audio_data)
        self.audio_worker.start()

        user_name = "друг"
        if isinstance(self.config, dict):
            user_name = self.config.get("user_name", "друг")
        self.initial_greeting_text = f"Привет {user_name}!"

        self.tts_thread.start_warmup(
            greeting_text=self.initial_greeting_text,
            is_whisper=self.is_whisper_mode
        )

    def on_warmup_completed(self):
        self.reveal_ui()
        QTimer.singleShot(1500, self.play_initial_greeting)

    def reveal_ui(self):
        if not self.ui_revealed:
            self.ui_revealed = True
            self.set_ui_interactive(True)
            self.title_btns_widget.show()
            self.title_btns_anim.start()
            self.left_panel.start_intro_animation(duration=3800)
            self.mini_left_panel.start_intro_animation(duration=3800)

    def play_initial_greeting(self):
        if not self.is_muted:
            self.tts_thread.play_cached_greeting()

    def start_vision(self):
        if self.vision_thread is not None and self.vision_thread.isRunning():
            return

        self.vision_thread = VisionThread(camera_index=0, parent=self)
        self.presence_manager = PresenceManager(timeout_seconds=600, parent=self)

        self.vision_thread.face_detected_signal.connect(self.presence_manager.process_face_status)
        self.vision_thread.gesture_detected_signal.connect(self.on_gesture_detected)
        self.vision_thread.deep_drowsiness_signal.connect(self.on_deep_drowsiness)
        self.vision_thread.frequent_blinking_signal.connect(self.on_frequent_blinking)

        self.presence_manager.user_left.connect(self.on_user_left)
        self.presence_manager.user_returned.connect(self.on_user_returned)
        self.presence_manager.unknown_user_detected.connect(self.on_unknown_user)

        self.vision_thread.start()

    def stop_vision(self):
        if self.presence_manager is not None:
            if hasattr(self.presence_manager, 'timer') and self.presence_manager.timer.isActive():
                self.presence_manager.timer.stop()
            self.presence_manager = None

        if self.vision_thread is not None:
            self.vision_thread.stop()
            self.vision_thread = None

    def on_vision_state_changed(self, enabled: bool):
        if enabled:
            QTimer.singleShot(3800, self.start_vision)
        else:
            QTimer.singleShot(2000, self.stop_vision)

    def on_unknown_user(self):
        cfg = load_config()
        modules = cfg.get("modules", {})
        face_rec_enabled = modules.get("face_recognition", modules.get("vision", False))
        if not face_rec_enabled:
            return

        current_frame = getattr(self.vision_thread, "current_frame", None) if self.vision_thread else None
        from services.telegram.notifier import send_security_alert
        send_security_alert(
            frame_or_path=current_frame,
            caption="⚠️ Внимание! Обнаружен посторонний пользователь. Заблокировать ПК?"
        )

        self.tts_thread.say("Внимание. Замечен посторонний.")

    def on_gesture_detected(self, gesture_name):
        cfg = load_config()
        if not cfg.get("modules", {}).get("gestures", False):
            return

        if gesture_name == "open_palm":
            SystemActions.media_play_pause()
        elif gesture_name == "fist":
            self.absence_start_time = time.time()
            if self.presence_manager:
                self.presence_manager.set_manual_absence(grace_period=10)
            SystemActions.lock_screen()
        elif gesture_name == "pointing":
            SystemActions.media_next_track()

    def speak_reply(self, text, is_whisper=False):
        if text and not getattr(self, 'is_muted', False):
            force_whisper = getattr(self, 'is_whisper_mode', False) or is_whisper
            self.tts_thread.say(text, is_whisper=force_whisper)

    def on_speech_recognized(self, text, audio_data=None):
        if not self.ui_revealed:
            return

        if getattr(self.right_panel, 'attached_file', None):
            self.chat_history.append(f"Вы (голос): {text}")
            msg = "У тебя прикреплен файл. Чтобы я его изучила, пожалуйста, напиши свой вопрос текстом и нажми 'Отправить'."
            self.chat_history.append(f"Астра: {msg}\n")
            self.speak_reply(msg)
            return

        text_low = text.lower()
        if any(w in text_low for w in ["заблокируй", "залочь", "заблокировать", "залочить"]):
            self.absence_start_time = time.time()
            if self.presence_manager:
                self.presence_manager.set_manual_absence(grace_period=10)

        self.left_panel.set_processing(True)
        self.mini_left_panel.set_processing(True)

        self.voice_worker = CommandWorker(self.command_parser, text, audio_data=audio_data, is_voice=True, parent=self)
        self.voice_worker.result_ready.connect(self.on_voice_command_finished)
        self.voice_worker.start()

    def on_wake_word_detected(self):
        self.left_panel.trigger_wake_effect()
        self.mini_left_panel.trigger_wake_effect()

    def on_tts_finished(self):
        self.left_panel.set_processing(False)
        self.mini_left_panel.set_processing(False)
        if getattr(self, 'pending_followup', False):
            self.pending_followup = False
            self.stt_thread.start_followup(timeout=3.0)

    def on_voice_command_finished(self, response):
        if response:
            is_whisper = False
            user_display = self.voice_worker.text
            if isinstance(response, dict):
                self.pending_followup = response.get("followup", False)
                chat_text = response.get("chat", "")
                voice_text = response.get("voice", "")
                emotion = response.get("emotion", "neutral")
                is_whisper = response.get("is_whisper", False)
                user_display = response.get("user_display", user_display)
            else:
                chat_text = voice_text = str(response)
                emotion = getattr(self.command_parser, "last_emotion", "neutral")

            self.left_panel.set_emotion(emotion)
            self.mini_left_panel.set_emotion(emotion)

            if user_display:
                self.chat_history.append(f"Вы (голос): {user_display}")

            if chat_text:
                self.chat_history.append(f"Астра: {chat_text}\n")

                if isinstance(response, dict) and "Список доступных вариантов обхода" in chat_text:
                    if not (self.right_panel.isVisible() and self.right_panel.maximumWidth() > 0):
                        self.toggle_chat()

            if voice_text:
                self.speak_reply(voice_text, is_whisper=is_whisper)
            else:
                self.left_panel.set_processing(False)
                self.mini_left_panel.set_processing(False)
        else:
            self.left_panel.set_processing(False)
            self.mini_left_panel.set_processing(False)
            if hasattr(self, 'voice_worker') and self.voice_worker.text:
                self.chat_history.append(f"Вы (голос): {self.voice_worker.text}")
            emotion = getattr(self.command_parser, "last_emotion", "neutral")
            self.left_panel.set_emotion(emotion)

    def send_message(self):
        if not self.ui_revealed:
            return

        text = self.input_field.text().strip()
        attached_file = self.right_panel.attached_file

        if text or attached_file:
            user_msg = text if text else "Изучи прикрепленный файл"

            if attached_file:
                filename = os.path.basename(attached_file)
                self.chat_history.append(f"Вы: {user_msg} [📎 {filename}]")
            else:
                self.chat_history.append(f"Вы: {user_msg}")

            text_low = text.lower()
            if any(w in text_low for w in ["заблокируй", "залочь", "заблокировать", "залочить"]):
                self.absence_start_time = time.time()
                if self.presence_manager:
                    self.presence_manager.set_manual_absence(grace_period=10)

            self.input_field.clear()
            self.input_field.setEnabled(False)
            self.send_button.setEnabled(False)
            self.right_panel.clear_attachment()

            self.text_worker = CommandWorker(self.command_parser, text, is_voice=False, attached_file=attached_file,
                                             parent=self)
            self.text_worker.result_ready.connect(self.on_text_command_finished)
            self.text_worker.start()

    def on_text_command_finished(self, response):
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()

        if response:
            if isinstance(response, dict):
                chat_text = response.get("chat", "") or response.get("voice", "")
                voice_text = response.get("voice", "")
                emotion = response.get("emotion", "neutral")
            else:
                chat_text = voice_text = str(response)
                emotion = getattr(self.command_parser, "last_emotion", "neutral")

            self.left_panel.set_emotion(emotion)
            self.mini_left_panel.set_emotion(emotion)

            if chat_text:
                self.chat_history.append(f"Астра: {chat_text}\n")
            if voice_text:
                self.speak_reply(voice_text, is_whisper=False)

    def on_stt_error(self, err):
        pass

    def closeEvent(self, event):
        event.ignore()
        self.close_animated()

    def shutdown(self):
        volume_ducker.force_restore()
        if hasattr(self, 'battery_timer') and self.battery_timer.isActive():
            self.battery_timer.stop()
        if hasattr(self, 'audio_worker') and self.audio_worker.isRunning():
            self.audio_worker.stop()
        if hasattr(self, 'tts_thread') and self.tts_thread.isRunning():
            self.tts_thread.stop()
        self.stop_vision()
        if hasattr(self, 'stt_thread') and self.stt_thread.isRunning():
            self.stt_thread.stop_thread()
        if hasattr(self, 'telegram_thread') and self.telegram_thread and self.telegram_thread.isRunning():
            self.telegram_thread.stop()
        if hasattr(self, 'command_parser') and hasattr(self.command_parser, 'reminder_manager'):
            self.command_parser.reminder_manager.stop_ringing()

    def toggle_settings(self):
        is_opening = not (self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0)
        if is_opening and self.right_panel.isVisible() and self.right_panel.maximumHeight() > 0:
            self._pending_action = "settings"
            self._do_toggle_chat(force_close=True)
        else:
            self._do_toggle_settings()

    def _do_toggle_settings(self, force_close=False):
        self.settings_anim_group.stop()
        self.settings_anim_group.clear()

        is_opening = not (self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0)
        if force_close:
            is_opening = False

        anim_settings_min = QPropertyAnimation(self.settings_panel, b"minimumWidth")
        anim_settings_min.setDuration(450)
        anim_settings_min.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim_settings_max = QPropertyAnimation(self.settings_panel, b"maximumWidth")
        anim_settings_max.setDuration(450)
        anim_settings_max.setEasingCurve(QEasingCurve.Type.OutCubic)

        cur_w = self.settings_panel.width() if self.settings_panel.isVisible() else 0
        target_w = self.width() - 20

        if is_opening:
            self.settings_panel.reset_border()
            self.settings_panel.setMinimumWidth(cur_w)
            self.settings_panel.setMaximumWidth(cur_w)
            self.settings_panel.show()

            anim_settings_min.setStartValue(cur_w)
            anim_settings_min.setEndValue(target_w)
            anim_settings_max.setStartValue(cur_w)
            anim_settings_max.setEndValue(target_w)
        else:
            self.settings_panel.reset_border()
            anim_settings_min.setStartValue(cur_w)
            anim_settings_min.setEndValue(0)
            anim_settings_max.setStartValue(cur_w)
            anim_settings_max.setEndValue(0)

        self.settings_anim_group.addAnimation(anim_settings_min)
        self.settings_anim_group.addAnimation(anim_settings_max)
        self.settings_anim_group.start()

    def _on_settings_anim_finished(self):
        if self.settings_panel.maximumWidth() == 0:
            self.settings_panel.hide()
            self.settings_panel.reset_border()
        else:
            self.settings_panel.fade_in_border()

        if self._pending_action == "chat":
            self._pending_action = None
            self._do_toggle_chat()

    def toggle_chat(self):
        if getattr(self, '_is_chat_animating', False):
            return

        is_opening = not (self.right_panel.isVisible() and self.right_panel.maximumHeight() > 0)
        if is_opening and self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0:
            self._pending_action = "chat"
            self._do_toggle_settings(force_close=True)
        else:
            self._do_toggle_chat()

    def _do_toggle_chat(self, force_close=False):
        if getattr(self, '_is_chat_animating', False):
            return

        is_opening = not (self.right_panel.isVisible() and self.right_panel.height() > 10)
        if force_close:
            is_opening = False

        if not is_opening and not self.right_panel.isVisible():
            return

        self._is_chat_animating = True

        if is_opening:
            self.right_panel.prepare_for_open()
            self.right_panel.setMinimumHeight(0)
            self.right_panel.setMaximumHeight(0)
            self.right_panel.show()

            self._animate_chat_slide(0, 280, self._on_chat_slide_opened)
        else:
            try:
                self.right_panel.fade_finished.disconnect()
            except TypeError:
                pass

            self.right_panel.fade_finished.connect(self._on_chat_fade_closed)
            self.right_panel.fade_out()

    def _animate_chat_slide(self, start_h, end_h, callback):
        self.chat_anim_group.stop()
        self.chat_anim_group.clear()

        anim_chat_min = QPropertyAnimation(self.right_panel, b"minimumHeight")
        anim_chat_min.setDuration(600)
        anim_chat_min.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_chat_min.setStartValue(start_h)
        anim_chat_min.setEndValue(end_h)

        anim_chat_max = QPropertyAnimation(self.right_panel, b"maximumHeight")
        anim_chat_max.setDuration(600)
        anim_chat_max.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_chat_max.setStartValue(start_h)
        anim_chat_max.setEndValue(end_h)

        self.chat_anim_group.addAnimation(anim_chat_min)
        self.chat_anim_group.addAnimation(anim_chat_max)

        try:
            self.chat_anim_group.finished.disconnect()
        except TypeError:
            pass

        self.chat_anim_group.finished.connect(callback)
        self.chat_anim_group.start()

    def _on_chat_slide_opened(self):
        try:
            self.right_panel.fade_finished.disconnect()
        except TypeError:
            pass

        def _finish_open():
            self._is_chat_animating = False

        self.right_panel.fade_finished.connect(_finish_open)
        self.right_panel.fade_in()

    def _on_chat_fade_closed(self):
        cur_h = self.right_panel.height()
        self._animate_chat_slide(cur_h, 0, self._on_chat_slide_closed)

    def _on_chat_slide_closed(self):
        self.right_panel.hide()
        self._is_chat_animating = False
        if self._pending_action == "settings":
            self._pending_action = None
            self._do_toggle_settings()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = QPoint()
            event.accept()