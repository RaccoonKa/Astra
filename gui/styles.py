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
    background-color: rgba(8, 8, 5, 0.95);
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

/* СТИЛИ ДЛЯ ПАНЕЛИ НАСТРОЕК */
QLabel#SettingsTitle {
    color: #fffde7;
}
QLabel#SectionTitle {
    color: #ffd700;
}
QLabel#SettingLabel {
    color: #c4a028;
}
QLineEdit#SettingInput {
    background-color: #050503;
    color: #fffde7;
    border: 1px solid #3a3010;
    border-radius: 6px;
    padding: 4px 8px;
}
QLineEdit#SettingInput:focus {
    border: 1px solid #c4a028;
}
QPushButton#InstructionBtn {
    background-color: transparent;
    color: #8c7320;
    border: none;
    padding: 2px 4px;
    font-size: 11px;
}
QPushButton#InstructionBtn:hover {
    color: #ffd700;
    text-decoration: underline;
}
QPushButton#SaveSettingsButton {
    background-color: #c4a028;
    color: #0d0a05;
    font-weight: bold;
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
}
QPushButton#SaveSettingsButton:hover {
    background-color: #ffd700;
}
QScrollArea#SettingsScroll {
    background: transparent;
    border: none;
}
QScrollArea#SettingsScroll > QWidget > QWidget {
    background: transparent;
}

/* ЭЛЕГАНТНЫЙ КАСТОМНЫЙ СКРОЛЛБАР */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #3a3010;
    min-height: 25px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #c4a028;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

/* СТИЛИ ЧЕКБОКСОВ */
QCheckBox#VisionCheckbox {
    color: #fffde7;
    spacing: 8px;
}
QCheckBox#VisionCheckbox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a3010;
    border-radius: 4px;
    background-color: #050503;
}
QCheckBox#VisionCheckbox::indicator:checked {
    background-color: #c4a028;
    border: 1px solid #ffd700;
}
QPushButton#BulbBtn {
    background-color: transparent;
    border: none;
    font-size: 14px;
    padding: 0px 4px;
}
QPushButton#BulbBtn:hover {
    font-size: 16px;
}
"""