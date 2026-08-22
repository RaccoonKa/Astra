import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction, QIcon, QPixmap


class SystemTray(QSystemTrayIcon):
    def __init__(self, window, app):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base_dir, "assets", "icon", "ico", "icon_round.ico")
        png_path = os.path.join(base_dir, "assets", "icon", "icon_round.png")

        tray_icon = QIcon()
        if os.path.exists(ico_path):
            tray_icon.addFile(ico_path)
        elif os.path.exists(png_path):
            tray_icon.addPixmap(QPixmap(png_path))
        else:
            tray_icon = app.windowIcon()

        super().__init__(tray_icon, parent=window)
        self.window = window
        self.app = app
        self.setToolTip("Астра")
        self.init_menu()

    def init_menu(self):
        menu = QMenu()

        show_action = QAction("Открыть окно", self)
        show_action.triggered.connect(self.show_window)
        menu.addAction(show_action)

        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self.on_tray_activated)

    def show_window(self):
        self.window.showNormal()
        self.window.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.show_window()