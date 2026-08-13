import os
import sys
import json
import math
import winreg
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QLinearGradient, QBrush, QFont, QFontDatabase


SPEECH_HINTS = {
    "autostart": "Включив автозапуск, я буду просыпаться одновременно с твоим компьютером! Тебе даже не придется искать мою иконку — я сразу буду тут, готова помогать.",
    "vision": "Если включишь эту функцию, я буду узнавать тебя в лицо! Смогу радостно здороваться при твоем возвращении и защищать систему от чужих глаз.",
    "gestures": "С жестами я смогу понимать тебя без слов! Покажешь кулак — заблокирую твой компьютер, чтобы никто не получил к нему доступ кроме тебя. Покажешь ладонь — поставлю музыку на паузу. Почти магия!",
    "gigachat": "Это мой главный ум и вдохновение! Вставив ключ Гигачата, ты дашь мне возможность болтать с тобой обо всём на свете, шутить и отвечать на любые вопросы.",
    "yandex": "Доверь мне свой плейлист! Я смогу запускать твою волну, включать треки под настроение и ставить лайки.",
    "weather": "Этот ключ нужен, чтобы я всегда знала, брать ли тебе зонтик. Я смогу рассказывать свежий прогноз погоды и температуру за окном!",
    "google": "Подключив сервисы Гугл, ты откроешь мне доступ к Ютубу и контактам. Я смогу искать и разворачивать видео на весь экран, а также помогать связываться с друзьями!"
}


class SettingsFrame(QFrame):
    speak_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.border_phase = 0.0

        font_path = os.path.join("assets", "fonts", "Schiffbauer-Regular.otf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            self.font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        else:
            self.font_family = "Arial"

        self.custom_font = QFont(self.font_family, 11)
        self.setFont(self.custom_font)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(base_dir, "personal_data", "configs", "config.json")
        self.google_creds_path = os.path.join(base_dir, "personal_data", "configs", "google", "credentials.json")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_border)
        self.timer.start(20)

        self.init_ui()
        self.load_settings()

    def _create_checkbox_row(self, checkbox, hint_key):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(checkbox)
        row.addStretch()

        bulb_btn = QPushButton("💡")
        bulb_btn.setObjectName("BulbBtn")
        bulb_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bulb_btn.clicked.connect(lambda: self.speak_requested.emit(SPEECH_HINTS[hint_key]))
        row.addWidget(bulb_btn)

        return row

    def _create_field_block(self, label_text, placeholder, hint_key):
        block = QVBoxLayout()
        block.setSpacing(5)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label_text)
        lbl.setObjectName("SettingLabel")
        lbl.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        top_row.addWidget(lbl)

        top_row.addStretch()

        instr_btn = QPushButton("💡 Инструкция")
        instr_btn.setObjectName("InstructionBtn")
        instr_btn.setFont(QFont(self.font_family, 9))
        instr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        instr_btn.clicked.connect(lambda: self.speak_requested.emit(SPEECH_HINTS[hint_key]))
        top_row.addWidget(instr_btn)

        block.addLayout(top_row)

        inp = QLineEdit()
        inp.setObjectName("SettingInput")
        inp.setFont(QFont(self.font_family, 10))
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(34)
        block.addWidget(inp)

        return block, inp, instr_btn

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        title = QLabel("Настройки Приложения")
        title.setObjectName("SettingsTitle")
        title.setFont(QFont(self.font_family, 15, QFont.Weight.Bold))
        main_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("SettingsScroll")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 6, 0)
        scroll_layout.setSpacing(14)

        system_title = QLabel("Система")
        system_title.setObjectName("SectionTitle")
        system_title.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        scroll_layout.addWidget(system_title)

        self.autostart_checkbox = QCheckBox("🚀 Автозапуск при включении ПК")
        self.autostart_checkbox.setObjectName("VisionCheckbox")
        self.autostart_checkbox.setFont(QFont(self.font_family, 10))
        self.autostart_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)

        row_autostart = self._create_checkbox_row(self.autostart_checkbox, "autostart")
        scroll_layout.addLayout(row_autostart)

        line0 = QFrame()
        line0.setFrameShape(QFrame.Shape.HLine)
        line0.setStyleSheet("color: #3a3010; background-color: #3a3010;")
        scroll_layout.addWidget(line0)

        vision_title = QLabel("Модуль Зрения")
        vision_title.setObjectName("SectionTitle")
        vision_title.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        scroll_layout.addWidget(vision_title)

        self.vision_checkbox = QCheckBox("👁 Распознавание лица")
        self.vision_checkbox.setObjectName("VisionCheckbox")
        self.vision_checkbox.setFont(QFont(self.font_family, 10))
        self.vision_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.vision_checkbox.toggled.connect(self._on_vision_toggled)

        row_vision = self._create_checkbox_row(self.vision_checkbox, "vision")
        scroll_layout.addLayout(row_vision)

        self.gestures_checkbox = QCheckBox("🖐 Отслеживание жестов рук")
        self.gestures_checkbox.setObjectName("VisionCheckbox")
        self.gestures_checkbox.setFont(QFont(self.font_family, 10))
        self.gestures_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)

        row_gestures = self._create_checkbox_row(self.gestures_checkbox, "gestures")
        scroll_layout.addLayout(row_gestures)

        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet("color: #3a3010; background-color: #3a3010;")
        scroll_layout.addWidget(line1)

        keys_title = QLabel("API Ключи")
        keys_title.setObjectName("SectionTitle")
        keys_title.setFont(QFont(self.font_family, 12, QFont.Weight.Bold))
        scroll_layout.addWidget(keys_title)

        box_giga, self.gigachat_input, self.gigachat_instr = self._create_field_block(
            "API ключ GigaChat:", "Вставьте ключ GigaChat...", "gigachat"
        )
        scroll_layout.addLayout(box_giga)

        box_ya, self.yandex_input, self.yandex_instr = self._create_field_block(
            "Токен Яндекс Музыки:", "Вставьте токен Яндекс Музыки...", "yandex"
        )
        scroll_layout.addLayout(box_ya)

        box_weather, self.weather_input, self.weather_instr = self._create_field_block(
            "API Ключ Погоды:", "Вставьте ключ OpenWeather...", "weather"
        )
        scroll_layout.addLayout(box_weather)

        box_goog, self.google_input, self.google_instr = self._create_field_block(
            "API ключ Google:", "Вставьте содержимое файла...", "google"
        )
        scroll_layout.addLayout(box_goog)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setFont(QFont(self.font_family, 10))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        btn_container = QHBoxLayout()
        btn_container.addStretch()

        self.save_btn = QPushButton("Сохранить настройки")
        self.save_btn.setObjectName("SaveSettingsButton")
        self.save_btn.setFont(QFont(self.font_family, 10, QFont.Weight.Bold))
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setFixedHeight(34)
        self.save_btn.setFixedWidth(190)
        self.save_btn.clicked.connect(self.save_settings)
        btn_container.addWidget(self.save_btn)

        btn_container.addStretch()
        main_layout.addLayout(btn_container)

        self.setLayout(main_layout)

    def _on_vision_toggled(self, checked: bool):
        self.gestures_checkbox.setEnabled(checked)
        if not checked:
            self.gestures_checkbox.setChecked(False)

    def _apply_windows_autostart(self, enabled: bool):
        app_name = "AstraAssistant"
        script_path = os.path.abspath(sys.argv[0])
        python_exe = sys.executable

        if script_path.endswith(".py"):
            pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
            exec_cmd = f'"{pythonw}" "{script_path}"' if os.path.exists(pythonw) else f'"{python_exe}" "{script_path}"'
        else:
            exec_cmd = f'"{script_path}"'

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exec_cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Autostart Reg Error]: {e}")

    def load_settings(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    api_keys = cfg.get("api_keys", {})
                    modules = cfg.get("modules", {})

                    self.autostart_checkbox.setChecked(cfg.get("autostart", False))

                    self.gigachat_input.setText(api_keys.get("gigachat", ""))
                    self.yandex_input.setText(api_keys.get("yandex_music_token", ""))
                    self.weather_input.setText(api_keys.get("weather", ""))

                    vision_on = modules.get("vision", True)
                    self.vision_checkbox.setChecked(vision_on)
                    self.gestures_checkbox.setEnabled(vision_on)
                    self.gestures_checkbox.setChecked(modules.get("gestures", True) if vision_on else False)
            except Exception as e:
                print(f"[Settings Load Error]: {e}")

        if os.path.exists(self.google_creds_path):
            try:
                with open(self.google_creds_path, "r", encoding="utf-8") as f:
                    creds_data = json.load(f)
                    self.google_input.setText(json.dumps(creds_data, ensure_ascii=False))
            except Exception as e:
                print(f"[Google Creds Load Error]: {e}")

    def save_settings(self):
        config_data = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except Exception as e:
                print(f"[Settings Read Error]: {e}")

        if "api_keys" not in config_data or not isinstance(config_data["api_keys"], dict):
            config_data["api_keys"] = {}
        if "modules" not in config_data or not isinstance(config_data["modules"], dict):
            config_data["modules"] = {}

        autostart_val = self.autostart_checkbox.isChecked()
        config_data["autostart"] = autostart_val
        self._apply_windows_autostart(autostart_val)

        config_data["api_keys"]["gigachat"] = self.gigachat_input.text().strip()
        config_data["api_keys"]["yandex_music_token"] = self.yandex_input.text().strip()
        config_data["api_keys"]["weather"] = self.weather_input.text().strip()

        config_data["modules"]["vision"] = self.vision_checkbox.isChecked()
        config_data["modules"]["gestures"] = self.gestures_checkbox.isChecked()

        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)

            google_text = self.google_input.text().strip()
            if google_text:
                os.makedirs(os.path.dirname(self.google_creds_path), exist_ok=True)
                try:
                    parsed_json = json.loads(google_text)
                    with open(self.google_creds_path, "w", encoding="utf-8") as f:
                        json.dump(parsed_json, f, ensure_ascii=False, indent=4)
                except json.JSONDecodeError:
                    with open(self.google_creds_path, "w", encoding="utf-8") as f:
                        f.write(google_text)

            self.status_label.setText("✓ Настройки сохранены!")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
            QTimer.singleShot(3000, lambda: self.status_label.setText(""))
        except Exception as e:
            self.status_label.setText("✕ Ошибка при сохранении")
            self.status_label.setStyleSheet("color: #F44336; font-size: 11px; font-weight: bold;")
            print(f"[Settings Save Error]: {e}")

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