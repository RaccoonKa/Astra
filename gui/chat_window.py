import os
import math
import random
import warnings
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFrame, QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QPoint, QRectF, QTimer, QPropertyAnimation,
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
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from comtypes import CoInitialize

warnings.filterwarnings("ignore", message="data discontinuity in recording")


class AudioVisualizerWorker(QThread):
    audio_data_signal = pyqtSignal(float, float, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

    def run(self):
        try:
            import soundcard as sc
            import warnings

            warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)

            default_speaker = sc.default_speaker()
            mic = sc.get_microphone(default_speaker.id, include_loopback=True)

            with mic.recorder(samplerate=44100) as recorder:
                while self.running:
                    data = recorder.record(numframes=2048)

                    samples = data[:, 0]
                    rms = float(np.sqrt(np.mean(samples ** 2)))

                    if rms < 0.01:
                        self.audio_data_signal.emit(0.0, 45.0, False)
                        continue

                    fft_vals = np.abs(np.fft.rfft(samples))
                    bass = float(np.sum(fft_vals[1:15]))

                    impulse = min(1.0, rms * 1.8 + bass * 0.004)

                    hue = 45.0
                    self.audio_data_signal.emit(impulse, hue, True)

        except ImportError:
            print("[Visualizer Error]: Установите библиотеку soundcard: pip install soundcard")
        except Exception as e:
            print(f"[Visualizer Error]: {e}")

    def stop(self):
        self.running = False
        self.wait()


class ArcMicButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.pulse = 0.0
        self.boost = 0.0
        self.is_listening = False
        self.is_speaking = False

        self.beat_impulse = 0.0
        self.target_impulse = 0.0
        self.music_hue = 45.0

        self.particles = []
        for _ in range(700):
            r_dist = random.gauss(72, 14)
            if r_dist < 36:
                r_dist = 36 + random.uniform(0, 8)
            self.particles.append({
                'r': r_dist,
                'angle': random.uniform(0, math.pi * 2),
                'speed': random.uniform(0.002, 0.008) * (1 if random.random() > 0.2 else -0.6),
                'size': random.uniform(0.6, 2.0),
                'color': "#ffffff",
                'alpha': random.randint(120, 255)
            })

        self.setMouseTracking(True)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

    def set_listening(self, state: bool):
        self.is_listening = state

    def set_speaking(self, state: bool):
        self.is_speaking = state

    def on_audio_data(self, impulse: float, hue: float, is_music: bool):
        if self.is_speaking:
            self.target_impulse = 0.0
            return

        if is_music:
            if impulse > self.target_impulse:
                self.target_impulse = impulse
            self.music_hue = hue

    def animate(self):
        self.pulse += 0.015

        self.beat_impulse += (self.target_impulse - self.beat_impulse) * 0.08
        self.target_impulse *= 0.93

        if self.is_listening:
            target_boost = 2.0
        elif self.is_speaking:
            target_boost = 1.2 + math.sin(self.pulse * 6.0) * 0.8
        else:
            target_boost = 0.0

        self.boost += (target_boost - self.boost) * 0.02

        effective_boost = max(self.boost, self.beat_impulse * 3.0)

        for p in self.particles:
            p['angle'] = (p['angle'] + p['speed'] * (1.0 + effective_boost)) % (math.pi * 2)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 130, 130
        p_val = math.sin(self.pulse) * (2.5 if self.is_speaking else 1.2)

        active_impulse = self.beat_impulse

        void_radius = 42 + (active_impulse * 20.0)

        void_shadow = QRadialGradient(cx, cy, void_radius)
        void_shadow.setColorAt(0.0, QColor(0, 0, 0, 255))
        void_shadow.setColorAt(0.85, QColor(0, 0, 0, 255))
        void_shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(void_shadow))
        painter.drawEllipse(QRectF(cx - void_radius, cy - void_radius, void_radius * 2, void_radius * 2))

        for p in self.particles:
            rad = p['r'] + (p_val * (1 if p['size'] > 1.2 else -1)) + (active_impulse * 25.0)
            px = cx + math.cos(p['angle']) * rad
            py = cy + math.sin(p['angle']) * rad

            if active_impulse > 0.01 and not self.is_speaking:
                p_hue = 42 + int(math.sin(p['angle'] * 5) * 6)
                col = QColor.fromHsv(p_hue, 120, 220)
            else:
                col = QColor(p['color'])

            col.setAlpha(int(p['alpha'] * (0.85 if self.boost < 0.6 and active_impulse < 0.01 else 1.0)))

            painter.setBrush(QBrush(col))

            sz = p['size'] + (active_impulse * 2.0)
            painter.drawEllipse(QRectF(px - sz / 2, py - sz / 2, sz, sz))


class ChatFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.border_phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_border)
        self.timer.start(20)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        self.chat_history = QTextEdit()
        self.chat_history.setObjectName("ChatHistory")
        self.chat_history.setReadOnly(True)
        layout.addWidget(self.chat_history)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setObjectName("InputField")
        self.input_field.setPlaceholderText("Введите команду...")
        input_layout.addWidget(self.input_field)

        self.send_button = QPushButton("Отправить")
        self.send_button.setObjectName("SendButton")
        input_layout.addWidget(self.send_button)

        layout.addLayout(input_layout)
        self.setLayout(layout)

    def animate_border(self):
        self.border_phase += 0.010
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        if w < 15 or h < 15:
            return

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
        painter.drawRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), 12, 12)


class BackgroundFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        for _ in range(1400):
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
        self.timer.start(20)

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
        painter.setClipPath(clip_path)

        painter.fillRect(self.rect(), QColor("#000000"))

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

        super().paintEvent(event)


class VolumeDucker:
    def __init__(self):
        self.saved_volumes = {}

    def duck(self):
        try:
            CoInitialize()
            self.saved_volumes.clear()
            sessions = AudioUtilities.GetAllSessions()

            for session in sessions:
                process = session.Process
                if process:
                    name = process.name().lower()

                    if "python" in name or "pycharm" in name:
                        continue

                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                    current_vol = volume.GetMasterVolume()
                    self.saved_volumes[process.pid] = current_vol

                    volume.SetMasterVolume(current_vol * 0.10, None)
        except Exception as e:
            print(f"[Volume Ducker Error]: {e}")

    def restore(self):
        try:
            CoInitialize()
            sessions = AudioUtilities.GetAllSessions()

            for session in sessions:
                process = session.Process
                if process and process.pid in self.saved_volumes:
                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)

                    saved_vol = self.saved_volumes[process.pid]
                    volume.SetMasterVolume(saved_vol, None)

            self.saved_volumes.clear()
        except Exception as e:
            print(f"[Volume Ducker Error]: {e}")


class MainWindow(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.drag_position = QPoint()
        self.ui_revealed = False
        self.command_parser = CommandParser()

        self.init_ui()
        self.init_audio()
        QTimer.singleShot(2000, self.init_vision)

    def init_ui(self):
        font_path = os.path.join("assets", "fonts", "Schiffbauer-Regular.otf")
        font_id = QFontDatabase.addApplicationFont(font_path)

        if font_id != -1:
            self.font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            self.custom_font = QFont(self.font_family, 11)
        else:
            print("[UI Warning]: Не удалось загрузить шрифт. Используем системный.")
            self.font_family = "Arial"
            self.custom_font = QFont(self.font_family, 11)

        self.setFont(self.custom_font)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
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
        title_btns_layout.setSpacing(0)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("TitleBtn")
        self.settings_btn.setFixedWidth(30)
        self.settings_btn.clicked.connect(self.toggle_settings)
        title_btns_layout.addWidget(self.settings_btn)

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
        close_btn.clicked.connect(self.hide)
        title_bar.addWidget(close_btn)

        right_area_layout.addLayout(title_bar)

        self.content_layout = QHBoxLayout()
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(0)

        self.left_panel = QFrame()
        self.left_panel.setObjectName("LeftPanel")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(4, 0, 0, 4)

        self.mic_btn = ArcMicButton()

        mic_container = QHBoxLayout()
        mic_container.addStretch()
        mic_container.addWidget(self.mic_btn)
        mic_container.addStretch()

        left_layout.addStretch()
        left_layout.addLayout(mic_container)
        left_layout.addStretch()

        author_label = QLabel("Created by Svetozar")
        author_label.setStyleSheet(
            f"font-family: '{self.font_family}'; color: rgba(255, 255, 255, 0.35); font-size: 13px; font-weight: 500;")
        left_layout.addWidget(author_label, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        self.left_panel.setLayout(left_layout)
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

        self.main_ui_opacity = QGraphicsOpacityEffect(self.left_panel)
        self.left_panel.setGraphicsEffect(self.main_ui_opacity)
        self.main_ui_opacity.setOpacity(0.0)

        self.title_btns_opacity = QGraphicsOpacityEffect(self.title_btns_widget)
        self.title_btns_widget.setGraphicsEffect(self.title_btns_opacity)
        self.title_btns_opacity.setOpacity(0.0)

        self.chat_opacity = QGraphicsOpacityEffect(self.right_panel)
        self.right_panel.setGraphicsEffect(self.chat_opacity)
        self.chat_opacity.setOpacity(0.0)

        self.settings_opacity = QGraphicsOpacityEffect(self.settings_panel)
        self.settings_panel.setGraphicsEffect(self.settings_opacity)
        self.settings_opacity.setOpacity(0.0)

        self.set_ui_interactive(False)

        self.anim_group = QParallelAnimationGroup(self)

    def set_ui_interactive(self, enabled: bool):
        self.settings_btn.setEnabled(enabled)
        self.toggle_chat_btn.setEnabled(enabled)
        self.mic_btn.setEnabled(enabled)

    def init_audio(self):
        self.stt_thread = STTThread(model_path="models/model_vosk", parent=self)
        self.stt_thread.text_recognized.connect(self.on_speech_recognized)
        self.stt_thread.listening_state_changed.connect(self.mic_btn.set_listening)
        self.stt_thread.error_occurred.connect(self.on_stt_error)
        self.stt_thread.start()

        self.tts_thread = TTSThread(parent=self)
        self.ducker = VolumeDucker()
        self.tts_thread.speaking_started.connect(self.on_initial_speech_started)
        self.tts_thread.speaking_started.connect(lambda: self.mic_btn.set_speaking(True))
        self.tts_thread.speaking_finished.connect(lambda: self.mic_btn.set_speaking(False))

        self.tts_thread.speaking_started.connect(lambda: self.stt_thread.set_speaking(True))
        self.tts_thread.speaking_finished.connect(lambda: self.stt_thread.set_speaking(False))

        self.tts_thread.speaking_started.connect(self.ducker.duck)
        self.tts_thread.speaking_finished.connect(self.ducker.restore)

        self.mic_btn.clicked.connect(self.stt_thread.trigger_manual_listen)

        self.audio_worker = AudioVisualizerWorker(parent=self)
        self.audio_worker.audio_data_signal.connect(self.mic_btn.on_audio_data)
        self.audio_worker.start()

        user_name = "друг"
        if isinstance(self.config, dict):
            user_name = self.config.get("user_name", "друг")

        self.tts_thread.start_with_greeting(f"Привет, {user_name}!")

    def init_vision(self):
        self.vision_thread = VisionThread(camera_index=0, parent=self)
        self.presence_manager = PresenceManager(timeout_seconds=300, parent=self)

        self.vision_thread.face_detected_signal.connect(self.presence_manager.process_face_status)
        self.vision_thread.gesture_detected_signal.connect(self.on_gesture_detected)

        user_name = "друг"
        if isinstance(self.config, dict):
            user_name = self.config.get("user_name", "друг")

        self.presence_manager.user_left.connect(SystemActions.lock_screen)
        self.presence_manager.user_returned.connect(lambda: self.tts_thread.say(f"С возвращением, {user_name}!"))
        self.presence_manager.unknown_user_detected.connect(self.on_unknown_user)

        self.vision_thread.start()

    def on_unknown_user(self):
        cfg = SystemActions._load_config() if hasattr(SystemActions, '_load_config') else {}
        if not cfg.get("modules", {}).get("vision", True):
            return

        self.tts_thread.say("Обнаружен посторонний пользователь. Блокирую систему.")
        SystemActions.lock_screen()

    def on_gesture_detected(self, gesture_name):
        cfg = SystemActions._load_config() if hasattr(SystemActions, '_load_config') else {}
        if not cfg.get("modules", {}).get("gestures", True):
            return

        if gesture_name == "open_palm":
            SystemActions.media_play_pause()
        elif gesture_name == "fist":
            SystemActions.lock_screen()
        elif gesture_name == "pointing":
            SystemActions.media_next_track()

    def on_initial_speech_started(self):
        if not self.ui_revealed:
            self.ui_revealed = True

            self.set_ui_interactive(True)

            self.reveal_anim_ui = QPropertyAnimation(self.main_ui_opacity, b"opacity")
            self.reveal_anim_ui.setDuration(1200)
            self.reveal_anim_ui.setStartValue(0.0)
            self.reveal_anim_ui.setEndValue(1.0)
            self.reveal_anim_ui.setEasingCurve(QEasingCurve.Type.InOutCubic)

            self.reveal_anim_btns = QPropertyAnimation(self.title_btns_opacity, b"opacity")
            self.reveal_anim_btns.setDuration(1200)
            self.reveal_anim_btns.setStartValue(0.0)
            self.reveal_anim_btns.setEndValue(1.0)
            self.reveal_anim_btns.setEasingCurve(QEasingCurve.Type.InOutCubic)

            self.reveal_group = QParallelAnimationGroup(self)
            self.reveal_group.addAnimation(self.reveal_anim_ui)
            self.reveal_group.addAnimation(self.reveal_anim_btns)
            self.reveal_group.start()

    def speak_reply(self, text):
        if text:
            self.tts_thread.say(text)

    def on_speech_recognized(self, text):
        if not self.ui_revealed:
            return

        response = self.command_parser.process_command(text)
        if response:
            self.speak_reply(response)

    def on_stt_error(self, err):
        pass

    def closeEvent(self, event):
        if hasattr(self, 'vision_thread'):
            self.vision_thread.stop()
        if hasattr(self, 'audio_worker'):
            self.audio_worker.stop()
        if hasattr(self, 'stt_thread'):
            self.stt_thread.stop_thread()
        super().closeEvent(event)

    def toggle_settings(self):
        self.anim_group.stop()
        self.anim_group.clear()

        def on_anim_finished():
            if self.settings_panel.maximumWidth() == 0:
                self.settings_panel.hide()
            try:
                self.anim_group.finished.disconnect(on_anim_finished)
            except TypeError:
                pass

        self.anim_group.finished.connect(on_anim_finished)

        anim_settings_min = QPropertyAnimation(self.settings_panel, b"minimumWidth")
        anim_settings_min.setDuration(850)
        anim_settings_min.setEasingCurve(QEasingCurve.Type.InOutQuart)

        anim_settings_max = QPropertyAnimation(self.settings_panel, b"maximumWidth")
        anim_settings_max.setDuration(850)
        anim_settings_max.setEasingCurve(QEasingCurve.Type.InOutQuart)

        anim_settings_op = QPropertyAnimation(self.settings_opacity, b"opacity")
        anim_settings_op.setDuration(850)
        anim_settings_op.setEasingCurve(QEasingCurve.Type.InOutQuart)

        if self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0:
            cur_w = self.settings_panel.width()
            anim_settings_min.setStartValue(cur_w)
            anim_settings_min.setEndValue(0)
            anim_settings_max.setStartValue(cur_w)
            anim_settings_max.setEndValue(0)
            anim_settings_op.setStartValue(self.settings_opacity.opacity())
            anim_settings_op.setEndValue(0.0)
        else:
            if self.right_panel.isVisible() and self.right_panel.maximumWidth() > 0:
                self.toggle_chat()

            cur_w = self.settings_panel.width() if (
                    self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0) else 0
            self.settings_panel.setMinimumWidth(cur_w)
            self.settings_panel.setMaximumWidth(cur_w)
            self.settings_panel.show()

            anim_settings_min.setStartValue(cur_w)
            anim_settings_min.setEndValue(375)
            anim_settings_max.setStartValue(cur_w)
            anim_settings_max.setEndValue(375)
            anim_settings_op.setStartValue(self.settings_opacity.opacity())
            anim_settings_op.setEndValue(1.0)

        self.anim_group.addAnimation(anim_settings_min)
        self.anim_group.addAnimation(anim_settings_max)
        self.anim_group.addAnimation(anim_settings_op)
        self.anim_group.start()

    def toggle_chat(self):
        self.anim_group.stop()
        self.anim_group.clear()

        def on_anim_finished():
            if self.right_panel.maximumWidth() == 0:
                self.right_panel.hide()
            try:
                self.anim_group.finished.disconnect(on_anim_finished)
            except TypeError:
                pass

        self.anim_group.finished.connect(on_anim_finished)

        anim_chat_min = QPropertyAnimation(self.right_panel, b"minimumWidth")
        anim_chat_min.setDuration(850)
        anim_chat_min.setEasingCurve(QEasingCurve.Type.InOutQuart)

        anim_chat_max = QPropertyAnimation(self.right_panel, b"maximumWidth")
        anim_chat_max.setDuration(850)
        anim_chat_max.setEasingCurve(QEasingCurve.Type.InOutQuart)

        anim_chat_op = QPropertyAnimation(self.chat_opacity, b"opacity")
        anim_chat_op.setDuration(850)
        anim_chat_op.setEasingCurve(QEasingCurve.Type.InOutQuart)

        if self.right_panel.isVisible() and self.right_panel.maximumWidth() > 0:
            cur_w = self.right_panel.width()
            anim_chat_min.setStartValue(cur_w)
            anim_chat_min.setEndValue(0)
            anim_chat_max.setStartValue(cur_w)
            anim_chat_max.setEndValue(0)
            anim_chat_op.setStartValue(self.chat_opacity.opacity())
            anim_chat_op.setEndValue(0.0)
        else:
            if self.settings_panel.isVisible() and self.settings_panel.maximumWidth() > 0:
                self.toggle_settings()

            cur_w = self.right_panel.width() if (
                    self.right_panel.isVisible() and self.right_panel.maximumWidth() > 0) else 0
            self.right_panel.setMinimumWidth(cur_w)
            self.right_panel.setMaximumWidth(cur_w)
            self.right_panel.show()

            anim_chat_min.setStartValue(cur_w)
            anim_chat_min.setEndValue(375)
            anim_chat_max.setStartValue(cur_w)
            anim_chat_max.setEndValue(375)
            anim_chat_op.setStartValue(self.chat_opacity.opacity())
            anim_chat_op.setEndValue(1.0)

        self.anim_group.addAnimation(anim_chat_min)
        self.anim_group.addAnimation(anim_chat_max)
        self.anim_group.addAnimation(anim_chat_op)
        self.anim_group.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def send_message(self):
        if not self.ui_revealed:
            return
        text = self.input_field.text().strip()
        if text:
            self.chat_history.append(f"Вы: {text}")
            response = self.command_parser.process_command(text)
            if response:
                self.chat_history.append(f"Астра: {response}\n")
                self.speak_reply(response)
            self.input_field.clear()