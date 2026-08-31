import os
import math
import time
import random
import atexit
import warnings
import threading
import numpy as np
import psutil
from services.telegram.notifier import send_security_alert
from services.telegram.telegram_bot import TelegramBotThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFrame, QFileDialog
)
from PyQt6.QtCore import (
    Qt, QPoint, QRectF, QTimer, QPropertyAnimation, QVariantAnimation,
    QEasingCurve, QParallelAnimationGroup, QThread, pyqtSignal
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QRadialGradient,
    QBrush, QPainterPath, QFont, QFontDatabase
)
from gui.styles import MAIN_STYLE
from gui.settings_window import SettingsFrame
from audio.stt import STTThread
from audio.tts import TTSThread
from core.nlp.command_parser import CommandParser
from core.system.actions import SystemActions
from core.vision.vision_provider import VisionThread
from core.vision.presence_manager import PresenceManager
from core.utils.config import get_resource_path, load_config
from core.utils.updater import UpdateCheckerThread
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from comtypes import CoInitialize, CoUninitialize

warnings.filterwarnings("ignore", message="data discontinuity in recording")


class AudioVisualizerWorker(QThread):
    audio_data_signal = pyqtSignal(float, float, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True
        self.peak_level = 0.02

    def run(self):
        import soundcard as sc
        warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)

        while self.running:
            try:
                default_speaker = sc.default_speaker()
                if not default_speaker:
                    self.msleep(300)
                    continue

                try:
                    mic = sc.get_microphone(default_speaker.id, include_loopback=True)
                except Exception:
                    mic = None

                if not mic:
                    loopbacks = [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]
                    if loopbacks:
                        mic = loopbacks[0]

                if not mic:
                    self.msleep(300)
                    continue

                with mic.recorder(samplerate=44100, blocksize=2048) as recorder:
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

            except Exception:
                self.msleep(300)

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

        self.pulse = 0.0
        self.boost = 0.0
        self.is_listening = False
        self.is_speaking = False

        self.beat_impulse = 0.0
        self.target_impulse = 0.0
        self.music_hue = 45.0

        self.intro_progress = 0.0
        self.particles = []
        self.total_particles = 350

        self.current_r = 255.0
        self.current_g = 255.0
        self.current_b = 255.0

        self.target_r = 255.0
        self.target_g = 255.0
        self.target_b = 255.0

        self.emotion_palette = {
            "angry": (235.0, 40.0, 70.0),
            "happy": (255.0, 215.0, 60.0),
            "sad": (70.0, 205.0, 230.0),
            "neutral": (255.0, 255.0, 255.0),
            "other": (255.0, 255.0, 255.0)
        }

        self.reset_emotion_timer = QTimer(self)
        self.reset_emotion_timer.setSingleShot(True)
        self.reset_emotion_timer.timeout.connect(self._reset_to_neutral)

        self._init_particles()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(24)

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

    def set_speaking(self, state: bool):
        self.is_speaking = state

    def set_emotion(self, emotion: str):
        target = self.emotion_palette.get(emotion, (255.0, 255.0, 255.0))
        self.target_r, self.target_g, self.target_b = target
        self.reset_emotion_timer.stop()
        if emotion != "neutral":
            self.reset_emotion_timer.start(10000)

    def _reset_to_neutral(self):
        self.target_r = 255.0
        self.target_g = 255.0
        self.target_b = 255.0

    def on_audio_data(self, impulse: float, hue: float, is_music: bool):
        if self.is_speaking:
            self.target_impulse = 0.0
            return

        if is_music:
            if impulse > self.target_impulse:
                self.target_impulse = impulse
            self.music_hue = hue
        else:
            self.target_impulse = 0.0

    def animate(self):
        self.pulse += 0.015
        self.beat_impulse += (self.target_impulse - self.target_impulse) * 0.08
        self.target_impulse *= 0.93

        self.current_r += (self.target_r - self.current_r) * 0.06
        self.current_g += (self.target_g - self.current_g) * 0.06
        self.current_b += (self.target_b - self.current_b) * 0.06

        if self.is_listening:
            target_boost = 2.0
        elif self.is_speaking:
            target_boost = 1.3 + math.sin(self.pulse * 4.0) * 0.6
        else:
            target_boost = 0.0

        self.boost += (target_boost - self.boost) * 0.05
        effective_boost = max(self.boost, self.beat_impulse * 2.8)

        for p in self.particles:
            p['accum_angle'] = (p['accum_angle'] + p['speed'] * (1.0 + effective_boost)) % (math.pi * 2)

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

        cur_r = int(self.current_r)
        cur_g = int(self.current_g)
        cur_b = int(self.current_b)

        painter.setPen(Qt.PenStyle.NoPen)

        for p in self.particles:
            if T < p['delay']:
                continue

            local_t = min(1.0, (T - p['delay']) / (1.0 - p['delay']))
            u = math.sin(local_t * (math.pi / 2))

            cur_angle = p['accum_angle']
            target_rad = p['r'] + (p_val * (1 if p['size'] > 1.2 else -1)) + (active_impulse * 24.0)
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

            if active_impulse > 0.01 and not self.is_speaking:
                p_hue = 42 + int(math.sin(cur_angle * 5) * 6)
                col = QColor.fromHsv(p_hue, 120, 220)
            else:
                col = QColor(cur_r, cur_g, cur_b)

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


class ChatFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.border_phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_border)
        self.timer.start(40)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)

        self.chat_history = QTextEdit()
        self.chat_history.setObjectName("ChatHistory")
        self.chat_history.setReadOnly(True)
        layout.addWidget(self.chat_history)

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
        layout.addWidget(self.file_container)

        input_layout = QHBoxLayout()

        self.attach_button = QPushButton("📎")
        self.attach_button.setObjectName("AttachBtn")
        self.attach_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_button.setFixedSize(30, 30)
        self.attach_button.clicked.connect(self.select_file)
        input_layout.addWidget(self.attach_button)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("InputField")
        self.input_field.setPlaceholderText("Введите команду...")
        input_layout.addWidget(self.input_field)

        self.send_button = QPushButton("Отправить")
        self.send_button.setObjectName("SendButton")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        input_layout.addWidget(self.send_button)

        layout.addLayout(input_layout)
        self.setLayout(layout)

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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        if w < 15 or h < 15:
            return

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

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_bg)
        self.timer.start(45)

    def animate_bg(self):
        self.wave_phase += 0.005
        for star in self.stars:
            star['phase'] += star['speed']
        for d in self.dust_cloud:
            d['twinkle_phase'] += d['twinkle_speed']
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

        self.vision_thread = None
        self.presence_manager = None

        self.absence_start_time = None
        self.warned_battery_50 = False
        self.warned_battery_25 = False
        self.warned_battery_tg_30 = False

        self.init_ui()
        self.init_audio()

        self.battery_timer = QTimer(self)
        self.battery_timer.timeout.connect(self.check_battery_status)
        self.battery_timer.start(45000)

        cfg_modules = self.config.get("modules", {}) if isinstance(self.config, dict) else {}
        if cfg_modules.get("vision", False):
            QTimer.singleShot(12500, self.start_vision)

        atexit.register(self.ducker.restore)

        self.telegram_thread = None
        QTimer.singleShot(8500, self._start_telegram_delayed)

        QTimer.singleShot(3000, self._check_updates)

    def _start_telegram_delayed(self):
        cfg_keys = self.config.get("api_keys", {}) if isinstance(self.config, dict) else {}
        if cfg_keys.get("telegram_token") and self.telegram_thread is None:
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

    def restart_telegram_bot(self):
        if hasattr(self, 'telegram_thread') and self.telegram_thread and self.telegram_thread.isRunning():
            self.telegram_thread.stop()
            self.telegram_thread = None

        cfg = load_config()
        if cfg.get("api_keys", {}).get("telegram_token"):
            self.telegram_thread = TelegramBotThread(parent=self)
            self.telegram_thread.start()

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
        self.resize(750, 450)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        container = BackgroundFrame()
        container.setObjectName("CentralWidget")
        container.setStyleSheet(MAIN_STYLE)

        container_layout = QHBoxLayout()
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

        self.exit_btn = QPushButton("⏻")
        self.exit_btn.setObjectName("ExitBtn")
        self.exit_btn.setFixedWidth(30)
        self.exit_btn.clicked.connect(self.exit_app)
        title_btns_layout.addWidget(self.exit_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("TitleBtn")
        self.settings_btn.setFixedWidth(30)
        self.settings_btn.clicked.connect(self.toggle_settings)
        title_btns_layout.addWidget(self.settings_btn)

        self.update_badge_btn = QPushButton("✨ v2.0.0 доступна!")
        self.update_badge_btn.setObjectName("UpdateNotificationBadge")
        self.update_badge_btn.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        self.update_badge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_badge_btn.clicked.connect(self.open_settings_for_update)
        self.update_badge_btn.hide()
        title_btns_layout.addWidget(self.update_badge_btn)

        self.toggle_chat_btn = QPushButton("💭")
        self.toggle_chat_btn.setObjectName("TitleBtn")
        self.toggle_chat_btn.setFixedWidth(30)
        self.toggle_chat_btn.clicked.connect(self.toggle_chat)
        title_btns_layout.addWidget(self.toggle_chat_btn)

        title_bar.addWidget(self.title_btns_widget)
        title_bar.addStretch()

        min_btn = QPushButton("—")
        min_btn.setObjectName("MinBtn")
        min_btn.setFixedWidth(30)
        min_btn.clicked.connect(self.showMinimized)
        title_bar.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedWidth(30)
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)

        right_area_layout.addLayout(title_bar)

        self.content_layout = QHBoxLayout()
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(0)

        self.left_panel = AstraMicWidget(self)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(15, 0, 0, 12)

        left_layout.addStretch()

        self.author_label = QLabel("Created by Svetozar")
        self.author_label.setStyleSheet(
            f"font-family: '{self.font_family}'; color: rgba(255, 255, 255, 0.0); font-size: 13px; font-weight: 500;"
        )
        left_layout.addWidget(self.author_label, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        self.content_layout.addWidget(self.left_panel)

        right_area_layout.addLayout(self.content_layout)
        self.right_area.setLayout(right_area_layout)
        container_layout.addWidget(self.right_area)

        self.settings_panel = SettingsFrame()
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setMinimumWidth(0)
        self.settings_panel.setMaximumWidth(0)
        self.settings_panel.hide()
        self.settings_panel.speak_requested.connect(self.speak_reply)
        self.settings_panel.vision_state_changed.connect(self.on_vision_state_changed)
        self.settings_panel.telegram_config_changed.connect(self.restart_telegram_bot)
        container_layout.addWidget(self.settings_panel)

        self.right_panel = ChatFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_panel.setMinimumWidth(0)
        self.right_panel.setMaximumWidth(0)
        self.right_panel.hide()
        container_layout.addWidget(self.right_panel)

        self.chat_history = self.right_panel.chat_history
        self.chat_history.setFont(QFont(self.font_family, 12))
        self.input_field = self.right_panel.input_field
        self.input_field.setFont(QFont(self.font_family, 12))
        self.send_button = self.right_panel.send_button
        self.send_button.setFont(QFont(self.font_family, 12))

        self.input_field.returnPressed.connect(self.send_message)
        self.send_button.clicked.connect(self.send_message)

        container.setLayout(container_layout)
        main_layout.addWidget(container)
        self.setLayout(main_layout)

        self.title_btns_widget.hide()
        self.set_ui_interactive(False)

        self.settings_anim_group = QParallelAnimationGroup(self)
        self.chat_anim_group = QParallelAnimationGroup(self)

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

    def exit_app(self):
        self.shutdown()
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().quit()

    def init_audio(self):
        self.stt_thread = STTThread(parent=self)
        self.stt_thread.text_recognized.connect(self.on_speech_recognized)
        self.stt_thread.listening_state_changed.connect(self.left_panel.set_listening)
        self.stt_thread.error_occurred.connect(self.on_stt_error)
        self.stt_thread.start()

        self.tts_thread = TTSThread(parent=self)
        self.tts_thread.warmup_finished.connect(self.on_warmup_completed)

        self.ducker = VolumeDucker()
        self.tts_thread.speaking_started.connect(lambda: self.left_panel.set_speaking(True))
        self.tts_thread.speaking_finished.connect(lambda: self.left_panel.set_speaking(False))

        self.tts_thread.speaking_started.connect(lambda: self.stt_thread.set_speaking(True))
        self.tts_thread.speaking_finished.connect(lambda: self.stt_thread.set_speaking(False))

        self.tts_thread.speaking_started.connect(self.ducker.duck)
        self.tts_thread.speaking_finished.connect(self.ducker.restore)

        self.left_panel.clicked.connect(self.stt_thread.trigger_manual_listen)

        self.audio_worker = AudioVisualizerWorker(parent=self)
        self.audio_worker.audio_data_signal.connect(self.left_panel.on_audio_data)
        self.audio_worker.start()

        user_name = "друг"
        if isinstance(self.config, dict):
            user_name = self.config.get("user_name", "друг")
        self.initial_greeting_text = f"Привет, {user_name}!"

        self.tts_thread.start_warmup(greeting_text=self.initial_greeting_text)

    def on_warmup_completed(self):
        self.reveal_ui()
        QTimer.singleShot(1500, self.play_initial_greeting)

    def reveal_ui(self):
        if not self.ui_revealed:
            self.ui_revealed = True
            self.set_ui_interactive(True)
            self.title_btns_widget.show()

            self.left_panel.start_intro_animation(duration=3800)

            self.author_anim = QVariantAnimation(self)
            self.author_anim.setDuration(2400)
            self.author_anim.setStartValue(0.0)
            self.author_anim.setEndValue(0.35)

            def _update_author_opacity(alpha):
                self.author_label.setStyleSheet(
                    f"font-family: '{self.font_family}'; color: rgba(255, 255, 255, {alpha:.2f}); font-size: 13px; font-weight: 500;"
                )

            self.author_anim.valueChanged.connect(_update_author_opacity)
            self.author_anim.start()

    def play_initial_greeting(self):
        self.tts_thread.play_cached_greeting()

    def start_vision(self):
        if self.vision_thread is not None and self.vision_thread.isRunning():
            return

        self.vision_thread = VisionThread(camera_index=0, parent=self)
        self.presence_manager = PresenceManager(timeout_seconds=60, parent=self)

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
        if text:
            self.tts_thread.say(text, is_whisper=is_whisper)

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

        self.voice_worker = CommandWorker(self.command_parser, text, audio_data=audio_data, is_voice=True, parent=self)
        self.voice_worker.result_ready.connect(self.on_voice_command_finished)
        self.voice_worker.start()

    def on_voice_command_finished(self, response):
        if response:
            is_whisper = False
            user_display = self.voice_worker.text
            if isinstance(response, dict):
                chat_text = response.get("chat", "")
                voice_text = response.get("voice", "")
                emotion = response.get("emotion", "neutral")
                is_whisper = response.get("is_whisper", False)
                user_display = response.get("user_display", user_display)
            else:
                chat_text = voice_text = str(response)
                emotion = getattr(self.command_parser, "last_emotion", "neutral")

            self.left_panel.set_emotion(emotion)

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
            else:
                chat_text = voice_text = str(response)

            if chat_text:
                self.chat_history.append(f"Астра: {chat_text}\n")
            if voice_text:
                self.speak_reply(voice_text, is_whisper=False)

    def on_stt_error(self, err):
        pass

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def shutdown(self):
        if hasattr(self, 'ducker'):
            self.ducker.restore()
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

    def toggle_settings(self):
        self.settings_anim_group.stop()
        self.settings_anim_group.clear()

        is_opening = not (self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0)

        if is_opening and self.right_panel.isVisible() and self.right_panel.maximumWidth() > 0:
            self.toggle_chat()

        def on_settings_finished():
            if self.settings_panel.maximumWidth() == 0:
                self.settings_panel.hide()

        try:
            self.settings_anim_group.finished.disconnect()
        except TypeError:
            pass

        self.settings_anim_group.finished.connect(on_settings_finished)

        anim_settings_min = QPropertyAnimation(self.settings_panel, b"minimumWidth")
        anim_settings_min.setDuration(600)
        anim_settings_min.setEasingCurve(QEasingCurve.Type.InOutQuart)

        anim_settings_max = QPropertyAnimation(self.settings_panel, b"maximumWidth")
        anim_settings_max.setDuration(600)
        anim_settings_max.setEasingCurve(QEasingCurve.Type.InOutQuart)

        cur_w = self.settings_panel.width() if self.settings_panel.isVisible() else 0

        if is_opening:
            self.settings_panel.setMinimumWidth(cur_w)
            self.settings_panel.setMaximumWidth(cur_w)
            self.settings_panel.show()

            anim_settings_min.setStartValue(cur_w)
            anim_settings_min.setEndValue(375)
            anim_settings_max.setStartValue(cur_w)
            anim_settings_max.setEndValue(375)
        else:
            anim_settings_min.setStartValue(cur_w)
            anim_settings_min.setEndValue(0)
            anim_settings_max.setStartValue(cur_w)
            anim_settings_max.setEndValue(0)

        self.settings_anim_group.addAnimation(anim_settings_min)
        self.settings_anim_group.addAnimation(anim_settings_max)
        self.settings_anim_group.start()

    def toggle_chat(self):
        self.chat_anim_group.stop()
        self.chat_anim_group.clear()

        is_opening = not (self.right_panel.isVisible() and self.right_panel.maximumWidth() > 0)

        if is_opening and self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0:
            self.toggle_settings()

        def on_chat_finished():
            if self.right_panel.maximumWidth() == 0:
                self.right_panel.hide()

        try:
            self.chat_anim_group.finished.disconnect()
        except TypeError:
            pass

        self.chat_anim_group.finished.connect(on_chat_finished)

        anim_chat_min = QPropertyAnimation(self.right_panel, b"minimumWidth")
        anim_chat_min.setDuration(600)
        anim_chat_min.setEasingCurve(QEasingCurve.Type.InOutQuart)

        anim_chat_max = QPropertyAnimation(self.right_panel, b"maximumWidth")
        anim_chat_max.setDuration(600)
        anim_chat_max.setEasingCurve(QEasingCurve.Type.InOutQuart)

        cur_w = self.right_panel.width() if self.right_panel.isVisible() else 0

        if is_opening:
            self.right_panel.setMinimumWidth(cur_w)
            self.right_panel.setMaximumWidth(cur_w)
            self.right_panel.show()

            anim_chat_min.setStartValue(cur_w)
            anim_chat_min.setEndValue(375)
            anim_chat_max.setStartValue(cur_w)
            anim_chat_max.setEndValue(375)
        else:
            anim_chat_min.setStartValue(cur_w)
            anim_chat_min.setEndValue(0)
            anim_chat_max.setStartValue(cur_w)
            anim_chat_max.setEndValue(0)

        self.chat_anim_group.addAnimation(anim_chat_min)
        self.chat_anim_group.addAnimation(anim_chat_max)
        self.chat_anim_group.start()

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