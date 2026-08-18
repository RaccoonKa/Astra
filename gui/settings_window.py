import os
import sys
import json
import math
import winreg
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QWidget, QComboBox
)
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, pyqtSignal,
    QVariantAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QLinearGradient, QBrush, QPainterPath,
    QFont, QFontDatabase
)


SPEECH_HINTS = {
    "autostart": "Включив автозапуск, я буду просыпаться одновременно с твоим компьютером! Тебе даже не придется искать мою иконку — я сразу буду тут, готова помогать.",
    "vpn_service": "Выбери, какую виртуальную сеть ты используешь! Я смогу автоматически запускать и переключать её по голосовой команде.",
    "vision": "Если включишь эту функцию, я буду узнавать тебя в лицо! Смогу радостно здороваться при твоем возвращении и защищать систему от чужих глаз.",
    "gestures": "С жестами я смогу понимать тебя без слов! Покажешь кулак — заблокирую твой компьютер, чтобы никто не получил к нему доступ кроме тебя. Покажешь ладонь — поставлю музыку на паузу. Почти магия!",
    "music_service": "Выбери, где мне включать музыку! Если переключатель включен — я буду ставить треки и запускать твою волну рекомендаций в Спотике, а если выключен — в +Яндексе. Однако ты можешь сказать: Астра, включи музыку на +Яндексе. И тогда даже если ты слушаешь на спотике, я смогу включить тебе музыку и на +Яндексе. Волшебство!",
    "gigachat": "Это мой главный ум и вдохновение! Вставив ключ Гигачата, ты дашь мне возможность болтать с тобой обо всём на свете, шутить и отвечать на любые вопросы.",
    "yandex": "Доверь мне свой плейлист! Я смогу запускать твою волну, включать треки под настроение и ставить лайки.",
    "spotify": "Здесь указываются айди клиента и ключ клиента из твоего личного кабинета Спотиф+ая. Заполни плашки и я смогу включать тебе музыку в Спотике. Послушаем классный музон?",
    "weather": "Этот ключ нужен, чтобы я всегда знала, брать ли тебе зонтик. Я смогу рассказывать свежий прогноз погоды и температуру за окном!",
    "google": "Подключив сервисы Гугл, ты откроешь мне доступ к Ютубу и контактам. Я смогу искать и разворачивать видео на весь экран, а также помогать связываться с друзьями!",
    "hdrezka": "Здесь ты можешь указать актуальное зеркало для этого сайта! Сайты иногда меняют адреса+, так что если фильмы перестанут открываться — просто обнови ссылку тут, и я буду искать по новому адресу.",
    "work_apps": "Укажи через запятую сайты или пути к программам, которые мне открывать, когда ты скажешь 'работа' или 'рабочий режим'!",
    "rest_apps": "Укажи через запятую сайты, фильмы или игры, которые мне открывать, когда ты скажешь 'отдых' или 'режим отдыха'!"
}


class NoScrollComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def wheelEvent(self, event):
        event.ignore()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        arrow_x = w - 16
        arrow_y = h / 2.0

        is_hovered = self.underMouse()
        pen_color = QColor("#ffd700") if is_hovered else QColor("#c4a028")
        pen = QPen(pen_color, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        path = QPainterPath()
        path.moveTo(arrow_x - 4, arrow_y - 2)
        path.lineTo(arrow_x, arrow_y + 2.5)
        path.lineTo(arrow_x + 4, arrow_y - 2)
        painter.drawPath(path)


class SmoothScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_pos = None
        self._current_pos = None
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_smooth_step)

    def wheelEvent(self, event):
        p_delta = event.pixelDelta().y()
        a_delta = event.angleDelta().y()

        if p_delta != 0:
            delta = p_delta * 1.5
        elif a_delta != 0:
            delta = a_delta * 0.8
        else:
            super().wheelEvent(event)
            return

        v_bar = self.verticalScrollBar()
        min_val = float(v_bar.minimum())
        max_val = float(v_bar.maximum())

        if self._target_pos is None:
            self._target_pos = float(v_bar.value())
            self._current_pos = float(v_bar.value())

        self._target_pos = max(min_val, min(self._target_pos - delta, max_val))

        if not self._timer.isActive():
            self._timer.start()

        event.accept()

    def _on_smooth_step(self):
        if self._target_pos is None:
            self._timer.stop()
            return

        v_bar = self.verticalScrollBar()
        diff = self._target_pos - self._current_pos

        if abs(diff) < 0.5:
            self._current_pos = self._target_pos
            v_bar.setValue(int(round(self._current_pos)))
            self._target_pos = None
            self._timer.stop()
        else:
            self._current_pos += diff * 0.20
            v_bar.setValue(int(round(self._current_pos)))


class ModernToggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = checked
        self._thumb_pos = 1.0 if checked else 0.0

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.valueChanged.connect(self._on_anim_step)

    def _on_anim_step(self, val):
        self._thumb_pos = float(val)
        self.update()

    def isChecked(self):
        return self._checked

    def setChecked(self, state: bool):
        if self._checked != state:
            self._checked = state
            self._anim.stop()
            self._anim.setStartValue(self._thumb_pos)
            self._anim.setEndValue(1.0 if state else 0.0)
            self._anim.start()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = h / 2.0

        bg_alpha = int(40 + self._thumb_pos * 180)
        bg_color = QColor(196, 160, 40, bg_alpha) if self._thumb_pos > 0.01 else QColor(30, 26, 15, 180)

        pen_color = QColor(255, 215, 0, int(60 + self._thumb_pos * 195))
        painter.setPen(QPen(pen_color, 1.2))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(QRectF(0.6, 0.6, w - 1.2, h - 1.2), r, r)

        thumb_radius = r - 2.5
        thumb_min_x = 2.5 + thumb_radius
        thumb_max_x = w - 2.5 - thumb_radius
        thumb_cx = thumb_min_x + self._thumb_pos * (thumb_max_x - thumb_min_x)
        thumb_cy = h / 2.0

        thumb_color = QColor(255, 255, 255) if self._thumb_pos > 0.5 else QColor(160, 145, 110)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(thumb_color))
        painter.drawEllipse(QPointF(thumb_cx, thumb_cy), thumb_radius, thumb_radius)


class SettingsFrame(QFrame):
    speak_requested = pyqtSignal(str)
    vision_state_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.border_phase = 0.0
        self.saved_vision_state = False

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

    def _create_hint_button(self, hint_key):
        btn = QPushButton("?")
        btn.setObjectName("HintCircleBtn")
        btn.setFont(QFont(self.font_family, 9, QFont.Weight.Bold))
        btn.setFixedSize(18, 18)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.speak_requested.emit(SPEECH_HINTS[hint_key]))
        return btn

    def _create_toggle_row(self, title_text, hint_key):
        row = QHBoxLayout()
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(10)

        lbl = QLabel(title_text)
        lbl.setObjectName("ToggleLabel")
        lbl.setFont(QFont(self.font_family, 11))
        row.addWidget(lbl)
        row.addStretch()

        hint_btn = self._create_hint_button(hint_key)
        row.addWidget(hint_btn)

        toggle = ModernToggle()
        row.addWidget(toggle)

        return row, toggle

    def _create_combo_row(self, label_text, items, hint_key):
        row = QHBoxLayout()
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(10)

        lbl = QLabel(label_text)
        lbl.setObjectName("ToggleLabel")
        lbl.setFont(QFont(self.font_family, 11))
        row.addWidget(lbl)
        row.addStretch()

        hint_btn = self._create_hint_button(hint_key)
        row.addWidget(hint_btn)

        combo = NoScrollComboBox()
        combo.setObjectName("SettingCombo")
        combo.setFont(QFont(self.font_family, 10))
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setFixedWidth(130)
        for name, key in items:
            combo.addItem(name, key)
        row.addWidget(combo)

        return row, combo

    def _create_field_block(self, label_text, placeholder, hint_key):
        block = QVBoxLayout()
        block.setContentsMargins(4, 3, 4, 3)
        block.setSpacing(5)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label_text)
        lbl.setObjectName("FieldLabel")
        lbl.setFont(QFont(self.font_family, 11))
        top_row.addWidget(lbl)
        top_row.addStretch()

        hint_btn = self._create_hint_button(hint_key)
        top_row.addWidget(hint_btn)
        block.addLayout(top_row)

        inp = QLineEdit()
        inp.setObjectName("SettingInput")
        inp.setFont(QFont(self.font_family, 11))
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(32)
        block.addWidget(inp)

        return block, inp

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        title = QLabel("Настройки")
        title.setObjectName("SettingsMainTitle")
        title.setFont(QFont(self.font_family, 15, QFont.Weight.Bold))
        main_layout.addWidget(title)

        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("SettingsScroll")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 6, 0)
        scroll_layout.setSpacing(10)

        card_sys = QFrame()
        card_sys.setObjectName("SettingsCard")
        layout_sys = QVBoxLayout(card_sys)
        layout_sys.setContentsMargins(10, 8, 10, 10)
        layout_sys.setSpacing(8)

        lbl_sys = QLabel("Система")
        lbl_sys.setObjectName("CardHeader")
        lbl_sys.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        layout_sys.addWidget(lbl_sys)

        row_auto, self.autostart_toggle = self._create_toggle_row("Автозапуск при включении", "autostart")
        layout_sys.addLayout(row_auto)

        vpn_items = [
            ("Не выбрано", "none"),
            ("Sota Connect", "sota"),
            ("Happ", "happ"),
            ("V2Ray / Xray", "v2ray"),
            ("WireGuard", "wireguard")
        ]
        row_vpn, self.vpn_combo = self._create_combo_row("VPN клиент:", vpn_items, "vpn_service")
        layout_sys.addLayout(row_vpn)

        scroll_layout.addWidget(card_sys)

        card_modes = QFrame()
        card_modes.setObjectName("SettingsCard")
        layout_modes = QVBoxLayout(card_modes)
        layout_modes.setContentsMargins(10, 8, 10, 10)
        layout_modes.setSpacing(8)

        lbl_modes = QLabel("Режимы (Работа / Отдых)")
        lbl_modes.setObjectName("CardHeader")
        lbl_modes.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        layout_modes.addWidget(lbl_modes)

        box_work, self.work_apps_input = self._create_field_block(
            "Работа (сайты/пути через запятую):", "https://github.com, C:\\...", "work_apps"
        )
        layout_modes.addLayout(box_work)

        box_rest, self.rest_apps_input = self._create_field_block(
            "Отдых (сайты/пути через запятую):", "https://youtube.com, ...", "rest_apps"
        )
        layout_modes.addLayout(box_rest)

        scroll_layout.addWidget(card_modes)

        card_music = QFrame()
        card_music.setObjectName("SettingsCard")
        layout_music = QVBoxLayout(card_music)
        layout_music.setContentsMargins(10, 8, 10, 10)
        layout_music.setSpacing(8)

        lbl_music = QLabel("Музыкальный сервис")
        lbl_music.setObjectName("CardHeader")
        lbl_music.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        layout_music.addWidget(lbl_music)

        row_music, self.spotify_toggle = self._create_toggle_row("Использовать Spotify (вместо Яндекс)", "music_service")
        layout_music.addLayout(row_music)
        scroll_layout.addWidget(card_music)

        card_vision = QFrame()
        card_vision.setObjectName("SettingsCard")
        layout_vision = QVBoxLayout(card_vision)
        layout_vision.setContentsMargins(10, 8, 10, 10)
        layout_vision.setSpacing(8)

        lbl_vision = QLabel("Модуль Зрения")
        lbl_vision.setObjectName("CardHeader")
        lbl_vision.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        layout_vision.addWidget(lbl_vision)

        row_vis, self.vision_toggle = self._create_toggle_row("Распознавание лица", "vision")
        self.vision_toggle.toggled.connect(self._on_vision_toggled)
        layout_vision.addLayout(row_vis)

        row_gest, self.gestures_toggle = self._create_toggle_row("Отслеживание жестов", "gestures")
        layout_vision.addLayout(row_gest)
        scroll_layout.addWidget(card_vision)

        card_keys = QFrame()
        card_keys.setObjectName("SettingsCard")
        layout_keys = QVBoxLayout(card_keys)
        layout_keys.setContentsMargins(10, 8, 10, 10)
        layout_keys.setSpacing(8)

        lbl_keys = QLabel("API Ключи и Сервисы")
        lbl_keys.setObjectName("CardHeader")
        lbl_keys.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        layout_keys.addWidget(lbl_keys)

        box_giga, self.gigachat_input = self._create_field_block(
            "API ключ GigaChat:", "Вставьте ключ GigaChat...", "gigachat"
        )
        layout_keys.addLayout(box_giga)

        box_ya, self.yandex_input = self._create_field_block(
            "Токен Яндекс Музыки:", "Вставьте токен Яндекс Музыки...", "yandex"
        )
        layout_keys.addLayout(box_ya)

        box_sp_id, self.spotify_id_input = self._create_field_block(
            "Spotify Client ID:", "Вставьте Spotify Client ID...", "spotify"
        )
        layout_keys.addLayout(box_sp_id)

        box_sp_secret, self.spotify_secret_input = self._create_field_block(
            "Spotify Client Secret:", "Вставьте Spotify Client Secret...", "spotify"
        )
        layout_keys.addLayout(box_sp_secret)

        box_weather, self.weather_input = self._create_field_block(
            "API Ключ Погоды:", "Вставьте ключ OpenWeather...", "weather"
        )
        layout_keys.addLayout(box_weather)

        box_goog, self.google_input = self._create_field_block(
            "API ключ Google:", "Вставьте JSON содержимое...", "google"
        )
        layout_keys.addLayout(box_goog)

        box_hdrezka, self.hdrezka_input = self._create_field_block(
            "Домен HDRezka:", "https://ru1.hdreskaz.top", "hdrezka"
        )
        layout_keys.addLayout(box_hdrezka)

        scroll_layout.addWidget(card_keys)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setFont(QFont(self.font_family, 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        btn_container = QHBoxLayout()
        btn_container.addStretch()

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setObjectName("SaveSettingsButton")
        self.save_btn.setFont(QFont(self.font_family, 11, QFont.Weight.Bold))
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setFixedHeight(34)
        self.save_btn.setFixedWidth(150)
        self.save_btn.clicked.connect(self.save_settings)
        btn_container.addWidget(self.save_btn)

        btn_container.addStretch()
        main_layout.addLayout(btn_container)

        self.setLayout(main_layout)

    def _on_vision_toggled(self, checked: bool):
        self.gestures_toggle.setEnabled(checked)
        if not checked:
            self.gestures_toggle.setChecked(False)

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

                    self.autostart_toggle.setChecked(cfg.get("autostart", False))

                    vpn_val = cfg.get("vpn_service", "none").lower()
                    idx = self.vpn_combo.findData(vpn_val)
                    if idx != -1:
                        self.vpn_combo.setCurrentIndex(idx)

                    use_sp = cfg.get("music_service", "yandex") == "spotify" or cfg.get("use_spotify", False)
                    self.spotify_toggle.setChecked(use_sp)

                    w_apps = cfg.get("work_apps", [])
                    self.work_apps_input.setText(", ".join(w_apps) if isinstance(w_apps, list) else str(w_apps))

                    r_apps = cfg.get("rest_apps", [])
                    self.rest_apps_input.setText(", ".join(r_apps) if isinstance(r_apps, list) else str(r_apps))

                    self.gigachat_input.setText(api_keys.get("gigachat", ""))
                    self.yandex_input.setText(api_keys.get("yandex_music_token", ""))
                    self.spotify_id_input.setText(api_keys.get("spotify_client_id", ""))
                    self.spotify_secret_input.setText(api_keys.get("spotify_client_secret", ""))
                    self.weather_input.setText(api_keys.get("weather", ""))
                    self.hdrezka_input.setText(cfg.get("hdrezka_domain", "https://ru1.hdreskaz.top"))

                    vision_on = modules.get("vision", False)
                    self.saved_vision_state = vision_on
                    self.vision_toggle.blockSignals(True)
                    self.vision_toggle.setChecked(vision_on)
                    self.vision_toggle.blockSignals(False)

                    self.gestures_toggle.setEnabled(vision_on)
                    self.gestures_toggle.setChecked(modules.get("gestures", False) if vision_on else False)
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

        autostart_val = self.autostart_toggle.isChecked()
        config_data["autostart"] = autostart_val
        self._apply_windows_autostart(autostart_val)

        config_data["vpn_service"] = self.vpn_combo.currentData()

        use_spotify_val = self.spotify_toggle.isChecked()
        config_data["music_service"] = "spotify" if use_spotify_val else "yandex"
        config_data["use_spotify"] = use_spotify_val

        work_raw = self.work_apps_input.text().strip()
        config_data["work_apps"] = [x.strip() for x in work_raw.split(",") if x.strip()] if work_raw else []

        rest_raw = self.rest_apps_input.text().strip()
        config_data["rest_apps"] = [x.strip() for x in rest_raw.split(",") if x.strip()] if rest_raw else []

        gigachat_key = self.gigachat_input.text().strip()
        config_data["api_keys"]["gigachat"] = gigachat_key
        config_data["api_keys"]["yandex_music_token"] = self.yandex_input.text().strip()
        config_data["api_keys"]["spotify_client_id"] = self.spotify_id_input.text().strip()
        config_data["api_keys"]["spotify_client_secret"] = self.spotify_secret_input.text().strip()
        config_data["api_keys"]["weather"] = self.weather_input.text().strip()

        config_data["modules"]["gigachat"] = bool(gigachat_key)

        hdrezka_domain = self.hdrezka_input.text().strip()
        config_data["hdrezka_domain"] = hdrezka_domain if hdrezka_domain else "https://ru1.hdreskaz.top"

        new_vision_val = self.vision_toggle.isChecked()
        config_data["modules"]["vision"] = new_vision_val
        config_data["modules"]["gestures"] = self.gestures_toggle.isChecked()

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

            self.status_label.setText("✓ Сохранено")
            self.status_label.setStyleSheet("color: #ffd700; font-size: 11px; font-weight: bold;")
            QTimer.singleShot(2500, lambda: self.status_label.setText(""))

            if new_vision_val and not self.saved_vision_state:
                self.speak_requested.emit("Подожди чуточку, открываю свои глазки!")
            elif not new_vision_val and self.saved_vision_state:
                self.speak_requested.emit("Закрываю глазки!")

            if new_vision_val != self.saved_vision_state:
                self.saved_vision_state = new_vision_val
                self.vision_state_changed.emit(new_vision_val)

        except Exception as e:
            self.status_label.setText("✕ Ошибка при сохранении")
            self.status_label.setStyleSheet("color: #ff5252; font-size: 11px; font-weight: bold;")
            print(f"[Settings Save Error]: {e}")

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