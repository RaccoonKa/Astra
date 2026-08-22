import os
import sys
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from core.utils.config import load_config
from gui.chat_window import MainWindow
from gui.tray import SystemTray
from gui.onboarding_wizard import OnboardingWizard


def get_ico_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(base_dir, "assets", "icon", "ico", "icon_round.ico")
    if os.path.exists(ico_path):
        return os.path.abspath(ico_path)
    fallback_ico = os.path.join(base_dir, "assets", "icon", "icon.ico")
    if os.path.exists(fallback_ico):
        return os.path.abspath(fallback_ico)
    return ""


def apply_native_windows_icon(hwnd, icon_path):
    if not icon_path or not os.path.exists(icon_path):
        return

    wm_seticon = 0x0080
    icon_small = 0
    icon_big = 1
    image_icon = 1
    lr_loadfromfile = 0x00000010
    gclp_hicon = -14
    gclp_hiconsm = -34

    h_icon_big = ctypes.windll.user32.LoadImageW(
        None, icon_path, image_icon, 256, 256, lr_loadfromfile
    )
    h_icon_small = ctypes.windll.user32.LoadImageW(
        None, icon_path, image_icon, 32, 32, lr_loadfromfile
    )

    if h_icon_big:
        ctypes.windll.user32.SendMessageW(hwnd, wm_seticon, icon_big, h_icon_big)
        try:
            ctypes.windll.user32.SetClassLongPtrW(hwnd, gclp_hicon, h_icon_big)
        except AttributeError:
            ctypes.windll.user32.SetClassLongW(hwnd, gclp_hicon, h_icon_big)

    if h_icon_small:
        ctypes.windll.user32.SendMessageW(hwnd, wm_seticon, icon_small, h_icon_small)
        try:
            ctypes.windll.user32.SetClassLongPtrW(hwnd, gclp_hiconsm, h_icon_small)
        except AttributeError:
            ctypes.windll.user32.SetClassLongW(hwnd, gclp_hiconsm, h_icon_small)


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

    ico_path = get_ico_path()
    app_icon = QIcon(ico_path) if ico_path else QIcon()
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

    hwnd = int(window.winId())
    apply_native_windows_icon(hwnd, ico_path)

    window.show()
    apply_native_windows_icon(hwnd, ico_path)

    tray = SystemTray(window, app)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()