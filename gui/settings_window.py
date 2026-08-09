import math
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QLinearGradient, QBrush


class SettingsFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.border_phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_border)
        self.timer.start(20)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Настройки")
        title.setStyleSheet("color: #fffde7; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        layout.addStretch()

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