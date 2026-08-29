import os
import io
import time
import json
import uuid
import qrcode
import requests
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPoint, QUrl
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QPainterPath, QFont, QPixmap, QDesktopServices
)
from core.utils.config import get_user_data_path, load_config


class TelegramPairDialog(QDialog):
    def __init__(self, font_family: str, parent=None):
        super().__init__(parent)
        self.font_family = font_family
        self.drag_position = QPoint()

        cfg = load_config()
        self.bot_token = cfg.get("api_keys", {}).get("telegram_token", "").strip()
        self.bot_username = ""

        if self.bot_token:
            try:
                resp = requests.get(f"https://api.telegram.org/bot{self.bot_token}/getMe", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    self.bot_username = data.get("result", {}).get("username", "")
            except Exception:
                pass

        self.session_path = Path(get_user_data_path("pairing_session.json"))

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(380, 500)

        self.token = uuid.uuid4().hex[:10]
        self.link = f"https://t.me/{self.bot_username}?start={self.token}" if self.bot_username else ""
        self.expires_at = time.time() + 180

        if self.bot_username:
            self._init_session_file()

        self.init_ui()

        if self.bot_username:
            self.poll_timer = QTimer(self)
            self.poll_timer.timeout.connect(self._check_pairing_status)
            self.poll_timer.start(1000)

    def _init_session_file(self):
        os.makedirs(self.session_path.parent, exist_ok=True)
        session_data = {
            "token": self.token,
            "expires_at": self.expires_at,
            "status": "pending"
        }
        with open(self.session_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=4)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_lbl = QLabel("Привязка Telegram")
        title_lbl.setFont(QFont(self.font_family, 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffd700; letter-spacing: 0.5px;")
        header.addWidget(title_lbl)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        if not self.bot_token or not self.bot_username:
            warn_lbl = QLabel("⚠️ Токен бота не найден или некорректен!\n\nСначала укажи токен от @BotFather в блоке 'API Ключи', нажми 'Сохранить', а затем открой это окно.")
            warn_lbl.setFont(QFont(self.font_family, 10))
            warn_lbl.setWordWrap(True)
            warn_lbl.setStyleSheet("color: #ffd700; line-height: 1.4;")
            layout.addWidget(warn_lbl)
            layout.addStretch()

            ok_btn = QPushButton("Понятно")
            ok_btn.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
            ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ok_btn.setFixedHeight(32)
            ok_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
                    color: #121008;
                    border: none;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background: #ffffff;
                }
            """)
            ok_btn.clicked.connect(self.reject)
            layout.addWidget(ok_btn)
            return

        desc_lbl = QLabel(f"Бот: @{self.bot_username}\nОтсканируй QR-код телефоном или перейди по кнопке:")
        desc_lbl.setFont(QFont(self.font_family, 10))
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #fffde7;")
        layout.addWidget(desc_lbl)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setPixmap(self._generate_qr_pixmap())
        layout.addWidget(self.qr_label)

        open_btn = QPushButton("Открыть в Telegram")
        open_btn.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setFixedHeight(32)
        open_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
                color: #121008;
                border: none;
                border-radius: 6px;
                padding: 4px 14px;
            }
            QPushButton:hover {
                background: #ffffff;
            }
        """)
        open_btn.clicked.connect(self._open_telegram_link)
        layout.addWidget(open_btn)

        link_lbl = QLabel(f'<a href="{self.link}" style="color: #c4a028; text-decoration: underline;">Прямая ссылка на привязку</a>')
        link_lbl.setFont(QFont(self.font_family, 9))
        link_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_lbl.setOpenExternalLinks(True)
        layout.addWidget(link_lbl)

        self.status_lbl = QLabel("Ожидание нажатия кнопки 'Старт'...")
        self.status_lbl.setFont(QFont(self.font_family, 10))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: #c4a028;")
        layout.addWidget(self.status_lbl)

    def _open_telegram_link(self):
        if self.link:
            QDesktopServices.openUrl(QUrl(self.link))

    def _generate_qr_pixmap(self) -> QPixmap:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=5,
            border=2
        )
        qr.add_data(self.link)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#ffd700", back_color="#080805")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")

        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        return pixmap

    def _check_pairing_status(self):
        if time.time() > self.expires_at:
            self.status_lbl.setText("Время действия истекло")
            self.status_lbl.setStyleSheet("color: #ff5252;")
            self.poll_timer.stop()
            return

        if self.session_path.exists():
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    session = json.load(f)
                if session.get("status") == "paired":
                    user_name = session.get("user_name", "")
                    self.status_lbl.setText(f"Успешно привязано к {user_name}!")
                    self.status_lbl.setStyleSheet("color: #4caf50; font-weight: bold;")
                    self.poll_timer.stop()
                    QTimer.singleShot(1200, self.accept)
            except Exception:
                pass

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