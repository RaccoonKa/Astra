MAIN_STYLE = """
QFrame#LeftPanel {
    background: transparent;
    border: none;
}
QFrame#RightPanel {
    background-color: rgba(8, 8, 5, 0.92);
    border: none;
    border-radius: 12px;
}
QFrame#SettingsPanel {
    background-color: rgba(8, 8, 5, 0.94);
    border: none;
    border-radius: 12px;
}
QTextEdit#ChatHistory {
    background-color: transparent;
    color: #fffde7;
    border: none;
    font-size: 13px;
}
QLineEdit#InputField {
    background-color: #050503;
    color: #fffde7;
    border: 1px solid #3a3010;
    border-radius: 8px;
    padding: 8px;
    font-size: 13px;
}
QPushButton#SendButton {
    background-color: #dcd8cf;
    color: #0d0a05;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton#SendButton:hover {
    background-color: #ffffff;
}
QPushButton#TitleBtn {
    background-color: transparent;
    color: #5c4e1a;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#TitleBtn:hover {
    background-color: rgba(92, 78, 26, 0.2);
    color: #ffd700;
}
QPushButton#MinBtn {
    background-color: transparent;
    color: #ffffff;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#MinBtn:hover {
    background-color: rgba(255, 255, 255, 0.15);
    color: #ffffff;
}
QPushButton#CloseBtn {
    background-color: transparent;
    color: #ffffff;
    font-size: 14px;
    padding: 2px 6px;
    border-radius: 4px;
}
QPushButton#CloseBtn:hover {
    background-color: #ff5252;
    color: #ffffff;
}

QLabel#SettingsMainTitle {
    color: #fffde7;
    letter-spacing: 0.5px;
}

QFrame#SettingsCard {
    background-color: rgba(18, 16, 10, 0.50);
    border: 1px solid rgba(196, 160, 40, 0.22);
    border-radius: 10px;
}

QLabel#CardHeader {
    color: #ffd700;
    letter-spacing: 1px;
    font-size: 11px;
    text-transform: uppercase;
}

QLabel#ToggleLabel {
    color: #fffde7;
    font-size: 12px;
}

QLabel#FieldLabel {
    color: rgba(255, 253, 231, 0.85);
    font-size: 11px;
}

QLineEdit#SettingInput {
    background-color: rgba(4, 4, 3, 0.85);
    color: #ffd700;
    border: 1px solid rgba(92, 78, 26, 0.5);
    border-radius: 6px;
    padding: 6px 10px;
    font-family: 'Consolas', 'Segoe UI', monospace;
    font-size: 11px;
}
QLineEdit#SettingInput:focus {
    border: 1px solid #ffd700;
    background-color: rgba(6, 6, 4, 0.95);
}

QComboBox#SettingCombo {
    background-color: rgba(4, 4, 3, 0.85);
    color: #ffd700;
    border: 1px solid rgba(92, 78, 26, 0.5);
    border-radius: 6px;
    padding: 4px 28px 4px 10px;
    font-size: 11px;
}
QComboBox#SettingCombo:focus {
    border: 1px solid #ffd700;
}
QComboBox#SettingCombo::drop-down {
    border: none;
    background: transparent;
    width: 0px;
}
QComboBox#SettingCombo::down-arrow {
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
    border-radius: 6px;
    outline: none;
}

QPushButton#HintCircleBtn {
    background-color: rgba(92, 78, 26, 0.25);
    color: #c4a028;
    border: 1px solid rgba(196, 160, 40, 0.35);
    border-radius: 9px;
    font-weight: bold;
    font-size: 10px;
}
QPushButton#HintCircleBtn:hover {
    background-color: rgba(255, 215, 0, 0.2);
    color: #ffd700;
    border: 1px solid #ffd700;
}

QPushButton#SaveSettingsButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ede8db, stop:1 #d6cebe);
    color: #121008;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 12px;
}
QPushButton#SaveSettingsButton:hover {
    background: #ffffff;
}

QScrollArea#SettingsScroll {
    background: transparent;
    border: none;
}
QScrollArea#SettingsScroll > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 4px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(92, 78, 26, 0.6);
    min-height: 25px;
    border-radius: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #ffd700;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
"""