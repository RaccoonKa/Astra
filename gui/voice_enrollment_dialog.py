import json
import sounddevice as sd
import vosk
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QPainterPath, QFont, QGuiApplication
)
from core.utils.config import get_resource_path


ENROLLMENT_PHRASES = [
    "Астра, включи мою любимую волну",
    "Какая сейчас погода и сколько градусов на улице",
    "Астра, запусти рабочий режим и закрой лишние окна"
]


class AudioRecorderThread(QThread):
    recording_finished = pyqtSignal(bytes)

    def __init__(self, duration=3.8, samplerate=16000, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.samplerate = samplerate
        self.is_recording = True

    def run(self):
        try:
            samples = int(self.duration * self.samplerate)
            audio = sd.rec(samples, samplerate=self.samplerate, channels=1, dtype='int16')
            sd.wait()
            if self.is_recording:
                self.recording_finished.emit(audio.tobytes())
        except Exception as e:
            print(f"[Recorder Error]: {e}", flush=True)

    def stop(self):
        self.is_recording = False
        try:
            sd.stop()
        except Exception:
            pass


class QuickNameRecognizerThread(QThread):
    name_recognized = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samplerate = 16000
        self.duration = 2.5

    def run(self):
        try:
            samples = int(self.duration * self.samplerate)
            audio = sd.rec(samples, samplerate=self.samplerate, channels=1, dtype='int16')
            sd.wait()

            model_path = get_resource_path("optimized_models", "model_vosk")
            vosk.SetLogLevel(-1)
            model = vosk.Model(model_path)
            rec = vosk.KaldiRecognizer(model, self.samplerate)

            if rec.AcceptWaveform(audio.tobytes()):
                res = json.loads(rec.Result())
            else:
                res = json.loads(rec.FinalResult())

            text = res.get("text", "").strip()
            if text:
                words = text.split()
                clean_name = words[-1].title()
                self.name_recognized.emit(clean_name)
            else:
                self.name_recognized.emit("")
        except Exception as e:
            print(f"[Name Recognition Error]: {e}", flush=True)
            self.name_recognized.emit("")


class VoiceEnrollmentDialog(QDialog):
    enrollment_completed = pyqtSignal()

    def __init__(self, verifier, is_owner=True, font_family="Arial", parent=None):
        super().__init__(parent)
        self.verifier = verifier
        self.is_owner = is_owner
        self.font_family = font_family
        self.drag_position = QPoint()

        self.step = 0 if not is_owner else 1
        self.current_phrase_idx = 0
        self.recorded_samples_count = 0

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(540, 480)

        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.x() + (screen.width() - 540) // 2, screen.y() + (screen.height() - 480) // 2)

        self.recorder_thread = None
        self.name_thread = None

        self.init_ui()
        self._update_step_view()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header_title = "Калибровка голоса создателя" if self.is_owner else "Добавление нового пользователя"
        self.title_lbl = QLabel(header_title)
        self.title_lbl.setFont(QFont(self.font_family, 13, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: #ffd700; letter-spacing: 0.5px;")
        header.addWidget(self.title_lbl)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.card = QFrame()
        self.card.setStyleSheet("""
            QFrame {
                background-color: rgba(14, 12, 7, 0.75);
                border: 1px solid rgba(196, 160, 40, 0.25);
                border-radius: 10px;
            }
        """)
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(16, 16, 16, 16)
        self.card_layout.setSpacing(12)

        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        self.status_lbl.setStyleSheet("color: #ffd700;")
        self.status_lbl.setWordWrap(True)
        self.card_layout.addWidget(self.status_lbl)

        self.desc_lbl = QLabel("")
        self.desc_lbl.setFont(QFont(self.font_family, 11))
        self.desc_lbl.setStyleSheet("color: #fffde7; line-height: 1.4;")
        self.desc_lbl.setWordWrap(True)
        self.card_layout.addWidget(self.desc_lbl)

        self.name_container = QFrame()
        self.name_container.setStyleSheet("background: transparent; border: none;")
        name_layout = QHBoxLayout(self.name_container)
        name_layout.setContentsMargins(0, 4, 0, 4)
        name_layout.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("SettingInput")
        self.name_input.setFont(QFont(self.font_family, 11))
        self.name_input.setFixedHeight(34)
        self.name_input.setPlaceholderText("Введи имя или назови вслух...")
        name_layout.addWidget(self.name_input, 1)

        self.mic_name_btn = QPushButton("🎙")
        self.mic_name_btn.setObjectName("AttachBtn")
        self.mic_name_btn.setFixedSize(34, 34)
        self.mic_name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_name_btn.clicked.connect(self._start_listen_name)
        name_layout.addWidget(self.mic_name_btn)
        self.card_layout.addWidget(self.name_container)

        self.phrase_box = QFrame()
        self.phrase_box.setStyleSheet("""
            QFrame {
                background-color: rgba(6, 6, 4, 0.85);
                border: 1px dashed rgba(255, 215, 0, 0.4);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        phrase_layout = QVBoxLayout(self.phrase_box)
        phrase_layout.setContentsMargins(10, 10, 10, 10)

        self.phrase_text_lbl = QLabel("")
        self.phrase_text_lbl.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        self.phrase_text_lbl.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        self.phrase_text_lbl.setWordWrap(True)
        self.phrase_text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phrase_layout.addWidget(self.phrase_text_lbl)
        self.card_layout.addWidget(self.phrase_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("UpdateProgressBar")
        self.progress_bar.setRange(0, 3)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.card_layout.addWidget(self.progress_bar)

        layout.addWidget(self.card, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        self.action_btn = QPushButton("Начать запись")
        self.action_btn.setObjectName("SaveSettingsButton")
        self.action_btn.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setFixedHeight(36)
        self.action_btn.setFixedWidth(180)
        self.action_btn.clicked.connect(self._on_action_clicked)
        bottom_row.addWidget(self.action_btn)
        layout.addLayout(bottom_row)

    def _update_step_view(self):
        if self.step == 0:
            self.status_lbl.setText("Подтверждение владельца системы 🔒")
            self.desc_lbl.setText(
                "Добавить новый профиль может только создатель. Нажми 'Подтвердить' и скажи любую фразу обычным голосом."
            )
            self.name_container.hide()
            self.phrase_box.hide()
            self.progress_bar.hide()
            self.action_btn.setText("Подтвердить")
        elif self.step == 1:
            self.status_lbl.setText("Знакомство ✨")
            target = "своё имя" if self.is_owner else "имя нового пользователя"
            self.desc_lbl.setText(f"Укажи {target}. Можно напечатать в строке или нажать на микрофон и назвать имя вслух:")
            self.name_container.show()
            self.phrase_box.hide()
            self.progress_bar.hide()
            self.action_btn.setText("Перейти к записи →")
        elif self.step == 2:
            self.status_lbl.setText(f"Калибровка голоса ({self.current_phrase_idx + 1}/3) 🎙")
            self.desc_lbl.setText("Произнеси фразу четко в микрофон обычным тоном:")
            self.name_container.hide()
            self.phrase_box.show()
            self.phrase_text_lbl.setText(f"«{ENROLLMENT_PHRASES[self.current_phrase_idx]}»")
            self.progress_bar.show()
            self.progress_bar.setValue(self.current_phrase_idx)
            self.action_btn.setText("Записать фразу")

    def _start_listen_name(self):
        self.mic_name_btn.setEnabled(False)
        self.name_input.setPlaceholderText("Слушаю имя...")
        self.name_thread = QuickNameRecognizerThread(self)
        self.name_thread.name_recognized.connect(self._on_name_recognized)
        self.name_thread.start()

    def _on_name_recognized(self, name):
        self.mic_name_btn.setEnabled(True)
        self.name_input.setPlaceholderText("Введи имя или назови вслух...")
        if name:
            self.name_input.setText(name)
            self.name_input.setFocus()

    def _on_action_clicked(self):
        if self.step == 0:
            self.action_btn.setEnabled(False)
            self.action_btn.setText("Слушаю владельца...")
            self.recorder_thread = AudioRecorderThread(duration=3.2, parent=self)
            self.recorder_thread.recording_finished.connect(self._verify_owner_recording)
            self.recorder_thread.start()

        elif self.step == 1:
            name = self.name_input.text().strip()
            if not name:
                self.name_input.setFocus()
                return
            self.user_name = name
            self.verifier.start_enrollment()
            self.step = 2
            self.current_phrase_idx = 0
            self._update_step_view()

        elif self.step == 2:
            self.action_btn.setEnabled(False)
            self.action_btn.setText("Идёт запись...")
            self.recorder_thread = AudioRecorderThread(duration=3.6, parent=self)
            self.recorder_thread.recording_finished.connect(self._on_phrase_recorded)
            self.recorder_thread.start()

    def _verify_owner_recording(self, audio_data):
        self.action_btn.setEnabled(True)
        is_rec, name, score, is_owner = self.verifier.verify(audio_data)

        if is_rec and is_owner:
            self.step = 1
            self._update_step_view()
        else:
            self.status_lbl.setText("Голос не опознан ❌")
            self.desc_lbl.setText("Верификация не пройдена. Пожалуйста, повтори попытку обычным голосом ближе к микрофону.")
            self.action_btn.setText("Попробовать снова")

    def _on_phrase_recorded(self, audio_data):
        ok, count = self.verifier.add_enrollment_sample(audio_data)
        self.action_btn.setEnabled(True)

        if ok:
            self.current_phrase_idx += 1
            if self.current_phrase_idx >= len(ENROLLMENT_PHRASES):
                self.verifier.commit_enrollment(self.user_name, is_owner=self.is_owner)
                self.enrollment_completed.emit()
                self.accept()
            else:
                self._update_step_view()
        else:
            self.desc_lbl.setText("Фраза получилась слишком тихой или короткой. Давай повторим её ещё разок:")
            self.action_btn.setText("Повторить фразу")

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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)

        painter.fillPath(path, QColor(8, 8, 5, 248))
        pen_border = QPen(QColor("#c4a028"), 1.4)
        painter.setPen(pen_border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)