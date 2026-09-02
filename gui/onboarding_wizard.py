import os
import math
import shutil
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QFrame, QFileDialog
)
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPoint, QPointF,
    QEasingCurve, QVariantAnimation
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QRadialGradient,
    QBrush, QPainterPath, QFont, QFontDatabase, QIcon
)

from core.utils.config import save_config, load_config, get_user_data_path, get_resource_path
from gui.settings_window import ModernToggle, NoScrollComboBox

WIZARD_STYLE = """
QFrame#WizardCard {
    background-color: rgba(16, 14, 8, 0.90);
    border: 1px solid rgba(196, 160, 40, 0.35);
    border-radius: 14px;
}

QLabel#WizardFieldLabel {
    color: #f7e8b6;
    font-size: 15px;
    font-weight: bold;
    letter-spacing: 0.4px;
    background: transparent;
    border: none;
}

QLabel#WizardDescText {
    color: #eee3cb;
    font-size: 15px;
    line-height: 1.5;
    background: transparent;
    border: none;
}

QLineEdit#WizardInput {
    background-color: rgba(5, 5, 3, 0.95);
    color: #ffffff;
    border: 1px solid rgba(196, 160, 40, 0.40);
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 15px;
    selection-background-color: #ffd700;
    selection-color: #000000;
}

QLineEdit#WizardInput:hover {
    border: 1px solid rgba(255, 215, 0, 0.70);
}

QLineEdit#WizardInput:focus {
    border: 1.5px solid #ffd700;
    background-color: rgba(10, 8, 4, 1.0);
}

QComboBox#WizardCombo {
    background-color: rgba(5, 5, 3, 0.95);
    color: #ffd700;
    border: 1px solid rgba(196, 160, 40, 0.40);
    border-radius: 8px;
    padding: 6px 28px 6px 14px;
    font-size: 15px;
}

QComboBox#WizardCombo:hover {
    border: 1px solid rgba(255, 215, 0, 0.70);
}

QComboBox#WizardCombo:focus {
    border: 1.5px solid #ffd700;
}

QComboBox#WizardCombo::drop-down {
    border: none;
    background: transparent;
    width: 0px;
}

QComboBox#WizardCombo::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}

QComboBox QAbstractItemView {
    background-color: #0d0a05;
    color: #ffd700;
    selection-background-color: #3a3010;
    selection-color: #ffffff;
    border: 1px solid #5c4e1a;
    border-radius: 8px;
    padding: 6px;
    font-size: 15px;
    outline: none;
}
"""


class WizardBackground(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.wave_phase = 0.0
        self.border_phase = 0.0

        self.stars = []
        for _ in range(60):
            self.stars.append({
                'rx': __import__('random').uniform(0.01, 0.99),
                'ry': __import__('random').uniform(0.01, 0.99),
                'size': __import__('random').uniform(0.6, 1.4),
                'phase': __import__('random').uniform(0, math.pi * 2),
                'speed': __import__('random').uniform(0.015, 0.035)
            })

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_bg)
        self.timer.start(20)

    def animate_bg(self):
        self.wave_phase += 0.008
        self.border_phase += 0.010
        for star in self.stars:
            star['phase'] += star['speed']
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), 16, 16)

        painter.fillPath(clip_path, QColor(6, 6, 4, 252))
        painter.setClipPath(clip_path)

        for star in self.stars:
            sx = star['rx'] * w
            sy = star['ry'] * h
            twinkle = (math.sin(star['phase']) + 1) / 2
            alpha = int(30 + twinkle * 200)
            col = QColor(255, 215, 0, alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col))
            painter.drawEllipse(QRectF(sx - star['size'], sy - star['size'], star['size'] * 2, star['size'] * 2))

        cx, cy = w / 2, h / 2
        dx = math.cos(self.border_phase) * w
        dy = math.sin(self.border_phase) * h

        border_grad = QLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy)
        border_grad.setColorAt(0.0, QColor("#181406"))
        border_grad.setColorAt(0.35, QColor("#3a3010"))
        border_grad.setColorAt(0.5, QColor("#5c4e1a"))
        border_grad.setColorAt(0.65, QColor("#3a3010"))
        border_grad.setColorAt(1.0, QColor("#181406"))

        pen_border = QPen(QBrush(border_grad), 1.6)
        painter.setPen(pen_border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.75, 0.75, w - 1.5, h - 1.5), 16, 16)


class StepIndicator(QWidget):
    def __init__(self, total_steps=4, current_step=0, parent=None):
        super().__init__(parent)
        self.total_steps = total_steps
        self.current_step = current_step
        self._visual_pos = float(current_step)
        self.setFixedHeight(36)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._on_anim_step)

    def _on_anim_step(self, val):
        self._visual_pos = float(val)
        self.update()

    def set_step(self, step):
        self.current_step = step
        self._anim.stop()
        self._anim.setStartValue(self._visual_pos)
        self._anim.setEndValue(float(step))
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        spacing = 50.0
        start_x = (self.width() - (self.total_steps - 1) * spacing) / 2.0
        cy = self.height() / 2.0

        end_x = start_x + (self.total_steps - 1) * spacing
        painter.setPen(QPen(QColor(50, 42, 20, 160), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(int(start_x), int(cy), int(end_x), int(cy))

        current_orb_x = start_x + self._visual_pos * spacing
        if current_orb_x > start_x:
            painter.setPen(QPen(QColor("#c4a028"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(start_x), int(cy), int(current_orb_x), int(cy))

        for i in range(self.total_steps):
            cx = start_x + i * spacing
            is_passed = i <= self._visual_pos

            node_col = QColor("#c4a028") if is_passed else QColor(40, 34, 16)
            border_col = QColor("#ffd700") if is_passed else QColor(70, 58, 26)

            painter.setPen(QPen(border_col, 1.2))
            painter.setBrush(QBrush(node_col))
            painter.drawEllipse(QPointF(cx, cy), 4.5, 4.5)

        halo = QRadialGradient(current_orb_x, cy, 18)
        halo.setColorAt(0.0, QColor(255, 215, 0, 150))
        halo.setColorAt(0.5, QColor(255, 215, 0, 45))
        halo.setColorAt(1.0, QColor(255, 215, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QPointF(current_orb_x, cy), 18, 18)

        core_grad = QLinearGradient(current_orb_x - 8, cy - 8, current_orb_x + 8, cy + 8)
        core_grad.setColorAt(0.0, QColor("#ffffff"))
        core_grad.setColorAt(0.6, QColor("#ffd700"))
        core_grad.setColorAt(1.0, QColor("#c4a028"))

        painter.setPen(QPen(QColor("#ffffff"), 1.2))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPointF(current_orb_x, cy), 7.5, 7.5)


class OnboardingWizard(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.drag_position = QPoint()

        self._init_window_icon()
        self.setWindowTitle("Astra")

        font_path = get_resource_path("assets", "fonts", "Schiffbauer-Regular.otf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            self.font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        else:
            self.font_family = "Arial"

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(700, 610)

        self.init_ui()

    def _init_window_icon(self):
        ico_path = get_resource_path("assets", "icon", "ico", "icon_round.ico")
        png_path = get_resource_path("assets", "icon", "icon_round.png")

        app_icon = None
        if os.path.exists(ico_path):
            app_icon = QIcon(ico_path)
        elif os.path.exists(png_path):
            app_icon = QIcon(png_path)

        if app_icon and not app_icon.isNull():
            self.setWindowIcon(app_icon)

    def init_ui(self):
        self.setStyleSheet(WIZARD_STYLE)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.bg = WizardBackground(self)
        bg_layout = QVBoxLayout(self.bg)
        bg_layout.setContentsMargins(34, 24, 34, 26)
        bg_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        header_title = QLabel("Инициализация Астры")
        header_title.setFont(QFont(self.font_family, 18, QFont.Weight.Bold))
        header_title.setStyleSheet("color: #ffd700; letter-spacing: 0.5px; background: transparent; border: none;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("color: #c4a028; background: transparent; border: none; font-size: 18px;")
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        bg_layout.addLayout(header_layout)

        self.step_indicator = StepIndicator(total_steps=4, current_step=0)
        bg_layout.addWidget(self.step_indicator)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent; border: none;")

        self.step1_widget = self._create_step1()
        self.step2_widget = self._create_step2()
        self.step3_widget = self._create_step3()
        self.step4_widget = self._create_step4()

        self.stack.addWidget(self.step1_widget)
        self.stack.addWidget(self.step2_widget)
        self.stack.addWidget(self.step3_widget)
        self.stack.addWidget(self.step4_widget)

        bg_layout.addWidget(self.stack, 1)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 10, 0, 0)

        self.back_btn = QPushButton("Назад")
        self.back_btn.setFont(QFont(self.font_family, 15))
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setFixedHeight(40)
        self.back_btn.setFixedWidth(130)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(22, 19, 11, 220);
                color: #c4a028;
                border: 1px solid rgba(196, 160, 40, 0.45);
                border-radius: 8px;
            }
            QPushButton:hover {
                background: rgba(45, 38, 18, 240);
                color: #ffd700;
                border: 1px solid #ffd700;
            }
        """)
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.hide()
        btn_row.addWidget(self.back_btn)

        btn_row.addStretch()

        self.next_btn = QPushButton("Далее →")
        self.next_btn.setFont(QFont(self.font_family, 15, QFont.Weight.Bold))
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFixedHeight(40)
        self.next_btn.setFixedWidth(150)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a88820, stop:1 #ffd700);
                color: #0d0a05;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffd700, stop:1 #ffffff);
            }
        """)
        self.next_btn.clicked.connect(self._go_next)
        btn_row.addWidget(self.next_btn)

        bg_layout.addLayout(btn_row)
        root_layout.addWidget(self.bg)

    def _create_card(self):
        card = QFrame()
        card.setObjectName("WizardCard")
        return card

    def _create_step1(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(14)

        desc = QLabel(
            "Давай познакомимся! Назови своё имя и укажи город, чтобы я правильно к тебе обращалась и сообщала точный прогноз погоды.")
        desc.setObjectName("WizardDescText")
        desc.setFont(QFont(self.font_family, 15))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        card = self._create_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 22)
        card_layout.setSpacing(16)

        row_name = QHBoxLayout()
        row_name.setContentsMargins(0, 0, 0, 0)
        row_name.setSpacing(12)
        lbl_name = QLabel("Как тебя зовут:")
        lbl_name.setObjectName("WizardFieldLabel")
        lbl_name.setFont(QFont(self.font_family, 15))
        row_name.addWidget(lbl_name)
        row_name.addStretch()

        self.name_input = QLineEdit()
        self.name_input.setObjectName("WizardInput")
        self.name_input.setFont(QFont(self.font_family, 15))
        self.name_input.setText(self.config.get("user_name", ""))
        self.name_input.setPlaceholderText("Твоё имя...")
        self.name_input.setFixedWidth(220)
        self.name_input.setFixedHeight(40)
        row_name.addWidget(self.name_input)
        card_layout.addLayout(row_name)

        row_gender = QHBoxLayout()
        row_gender.setContentsMargins(0, 0, 0, 0)
        row_gender.setSpacing(12)
        lbl_gender = QLabel("Твой пол (для согласования):")
        lbl_gender.setObjectName("WizardFieldLabel")
        lbl_gender.setFont(QFont(self.font_family, 15))
        row_gender.addWidget(lbl_gender)
        row_gender.addStretch()

        self.gender_combo = NoScrollComboBox()
        self.gender_combo.setObjectName("WizardCombo")
        self.gender_combo.setFont(QFont(self.font_family, 15))
        self.gender_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gender_combo.addItem("Мужской", "male")
        self.gender_combo.addItem("Женский", "female")
        self.gender_combo.setFixedWidth(220)
        self.gender_combo.setFixedHeight(40)
        idx_g = self.gender_combo.findData(self.config.get("user_gender", "male"))
        if idx_g != -1:
            self.gender_combo.setCurrentIndex(idx_g)
        row_gender.addWidget(self.gender_combo)
        card_layout.addLayout(row_gender)

        row_city = QHBoxLayout()
        row_city.setContentsMargins(0, 0, 0, 0)
        row_city.setSpacing(12)
        lbl_city = QLabel("Твой город (для погоды):")
        lbl_city.setObjectName("WizardFieldLabel")
        lbl_city.setFont(QFont(self.font_family, 15))
        row_city.addWidget(lbl_city)
        row_city.addStretch()

        self.city_input = QLineEdit()
        self.city_input.setObjectName("WizardInput")
        self.city_input.setFont(QFont(self.font_family, 15))
        self.city_input.setText(self.config.get("city", ""))
        self.city_input.setPlaceholderText("Например: Москва...")
        self.city_input.setFixedWidth(220)
        self.city_input.setFixedHeight(40)
        row_city.addWidget(self.city_input)
        card_layout.addLayout(row_city)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _create_step2(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(14)

        desc = QLabel(
            "Подключи мой цифровой разум (GigaChat), чтобы я могла поддержать любой диалог, понимать сложный контекст и помогать с задачами.")
        desc.setObjectName("WizardDescText")
        desc.setFont(QFont(self.font_family, 15))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        card = self._create_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 22)
        card_layout.setSpacing(14)

        lbl_giga = QLabel("Авторизационный ключ GigaChat API:")
        lbl_giga.setObjectName("WizardFieldLabel")
        lbl_giga.setFont(QFont(self.font_family, 15))
        card_layout.addWidget(lbl_giga)

        self.giga_input = QLineEdit()
        self.giga_input.setObjectName("WizardInput")
        self.giga_input.setFont(QFont("Consolas", 14))
        self.giga_input.setText(self.config.get("api_keys", {}).get("gigachat", ""))
        self.giga_input.setPlaceholderText("Вставь строку Base64...")
        self.giga_input.setFixedHeight(40)
        card_layout.addWidget(self.giga_input)

        lbl_weather = QLabel("API Ключ OpenWeather (необязательно):")
        lbl_weather.setObjectName("WizardFieldLabel")
        lbl_weather.setFont(QFont(self.font_family, 15))
        card_layout.addWidget(lbl_weather)

        self.weather_input = QLineEdit()
        self.weather_input.setObjectName("WizardInput")
        self.weather_input.setFont(QFont("Consolas", 14))
        self.weather_input.setText(self.config.get("api_keys", {}).get("weather", ""))
        self.weather_input.setPlaceholderText("Ключ от openweathermap.org...")
        self.weather_input.setFixedHeight(40)
        card_layout.addWidget(self.weather_input)

        hint = QLabel("💡 Ключи всегда можно добавить или изменить позже в настройках ⚙️.")
        hint.setFont(QFont(self.font_family, 13))
        hint.setStyleSheet("color: #b0995a; background: transparent; border: none;")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _create_step3(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(14)

        desc = QLabel("Настрой модули компьютерного зрения и фоновые возможности Астры под свои предпочтения.")
        desc.setObjectName("WizardDescText")
        desc.setFont(QFont(self.font_family, 15))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        card = self._create_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 22)
        card_layout.setSpacing(16)

        mods = self.config.get("modules", {})

        def make_row(title_text, checked_val):
            row = QHBoxLayout()
            lbl = QLabel(title_text)
            lbl.setObjectName("WizardFieldLabel")
            lbl.setFont(QFont(self.font_family, 15))
            row.addWidget(lbl)
            row.addStretch()
            toggle = ModernToggle(checked=checked_val)
            row.addWidget(toggle)
            return row, toggle

        r1, self.tg_toggle = make_row("Телеграм-пульт управления",
                                      self.config.get("api_keys", {}).get("telegram_admin_id", 0) != 0)
        r2, self.face_toggle = make_row("Распознавание владельца (Face ID)", mods.get("face_recognition", False))

        self.add_face_btn_wizard = QPushButton("📸 Загрузить моё фото")
        self.add_face_btn_wizard.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        self.add_face_btn_wizard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_face_btn_wizard.setStyleSheet("""
            QPushButton {
                background: rgba(92, 78, 26, 0.25);
                color: #ffd700;
                border: 1px solid rgba(196, 160, 40, 0.40);
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: rgba(255, 215, 0, 0.2);
                border: 1px solid #ffd700;
            }
        """)
        self.add_face_btn_wizard.clicked.connect(self._add_owner_face)

        row_face_btn = QHBoxLayout()
        row_face_btn.setContentsMargins(0, 0, 0, 4)
        row_face_btn.addWidget(self.add_face_btn_wizard)
        row_face_btn.addStretch()

        r3, self.gest_toggle = make_row("Управление ПК жестами рук", mods.get("gestures", False))
        r4, self.eye_toggle = make_row("Контроль усталости глаз", mods.get("eye_tracking", False))
        r5, self.auto_toggle = make_row("Автозапуск при старте Windows", self.config.get("autostart", False))

        card_layout.addLayout(r1)
        card_layout.addLayout(r2)
        card_layout.addLayout(row_face_btn)
        card_layout.addLayout(r3)
        card_layout.addLayout(r4)
        card_layout.addLayout(r5)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _add_owner_face(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Выбери свои лучшие фотки ✨", "", "Images (*.png *.jpg *.jpeg)")
        if files:
            face_dir = os.path.normpath(get_user_data_path("..", "owner_face"))
            os.makedirs(face_dir, exist_ok=True)
            count = 0
            for f in files:
                try:
                    shutil.copy(f, os.path.join(face_dir, os.path.basename(f)))
                    count += 1
                except Exception:
                    pass
            self.add_face_btn_wizard.setText(f"✓ Загружено фото: {count} шт.")
            self.add_face_btn_wizard.setStyleSheet("""
                QPushButton {
                    background: rgba(46, 125, 50, 0.4); 
                    color: #a5d6a7; 
                    border: 1px solid #4caf50; 
                    border-radius: 8px; 
                    padding: 6px 14px;
                }
            """)

    def _create_step4(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 16, 4, 4)
        layout.setSpacing(16)

        title = QLabel("Всё готово к запуску! 🌟")
        title.setFont(QFont(self.font_family, 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffd700; background: transparent; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Базовая калибровка завершена. Теперь я живу в твоём компьютере и готова помогать!\n\n"
            "• Нажми на сферу или назови меня по имени, чтобы отдать голосовую команду.\n"
            "• В панели настроек ⚙️ можно в любой момент подключить Яндекс Музыку, Spotify или Умный Дом.\n\n"
            "Приятного использования!"
        )
        desc.setObjectName("WizardDescText")
        desc.setFont(QFont(self.font_family, 15))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()
        return widget

    def _save_current_data(self):
        cfg = load_config()
        if "api_keys" not in cfg:
            cfg["api_keys"] = {}
        if "modules" not in cfg:
            cfg["modules"] = {}

        cfg["user_name"] = self.name_input.text().strip() or "друг"
        cfg["user_gender"] = self.gender_combo.currentData()
        cfg["city"] = self.city_input.text().strip() or "Калининград"

        giga_key = self.giga_input.text().strip()
        cfg["api_keys"]["gigachat"] = giga_key
        cfg["modules"]["gigachat"] = bool(giga_key)
        cfg["api_keys"]["weather"] = self.weather_input.text().strip()

        face_on = self.face_toggle.isChecked()
        gest_on = self.gest_toggle.isChecked()
        eye_on = self.eye_toggle.isChecked()

        cfg["modules"]["face_recognition"] = face_on
        cfg["modules"]["gestures"] = gest_on
        cfg["modules"]["eye_tracking"] = eye_on
        cfg["modules"]["vision"] = face_on or gest_on or eye_on
        cfg["autostart"] = self.auto_toggle.isChecked()

        cfg["first_run"] = False
        cfg["is_configured"] = True
        save_config(cfg)
        self.config = cfg

    def _go_next(self):
        cur_idx = self.stack.currentIndex()
        if cur_idx < self.stack.count() - 1:
            self._save_current_data()
            next_idx = cur_idx + 1
            self.stack.setCurrentIndex(next_idx)
            self.step_indicator.set_step(next_idx)
            self.back_btn.show()

            if next_idx == self.stack.count() - 1:
                self.next_btn.setText("Полетели!")
        else:
            self._save_current_data()
            self.accept()

    def _go_back(self):
        cur_idx = self.stack.currentIndex()
        if cur_idx > 0:
            next_idx = cur_idx - 1
            self.stack.setCurrentIndex(next_idx)
            self.step_indicator.set_step(next_idx)
            self.next_btn.setText("Далее →")
            if next_idx == 0:
                self.back_btn.hide()

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