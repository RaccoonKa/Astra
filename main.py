import os
import sys
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from personal_data.configs.config import load_config
from gui.chat_window import MainWindow
from gui.tray import SystemTray
from gui.onboarding_wizard import OnboardingWizard


def main():
    myappid = 'svetozar.astra.voiceassistant.1.0'
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Astra")
    app.setApplicationDisplayName("Astra")
    app.setQuitOnLastWindowClosed(False)

    app_icon = QIcon(os.path.join("assets", "icon", "ico", "icon_round.ico"))
    app.setWindowIcon(app_icon)

    config = load_config()

    is_first_run = config.get("first_run", True) and not config.get("is_configured", False)
    if is_first_run:
        wizard = OnboardingWizard(config)
        wizard.exec()
        config = load_config()

    window = MainWindow(config)
    window.setWindowTitle("Astra")
    window.setWindowIcon(app_icon)
    window.show()

    tray = SystemTray(window, app)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()