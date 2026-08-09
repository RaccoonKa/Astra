from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QStyle
from PyQt6.QtGui import QAction

class SystemTray(QSystemTrayIcon):
    def __init__(self, window, app):
        icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        super().__init__(icon, parent=window)
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