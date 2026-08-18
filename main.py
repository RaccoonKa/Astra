import sys
import traceback
from PyQt6.QtWidgets import QApplication
from personal_data.configs.config import load_config
from gui.chat_window import MainWindow
from gui.tray import SystemTray

def exception_hook(exctype, value, tb):
    print("Критическая ошибка:")
    traceback.print_exception(exctype, value, tb)
    print("-"*20 + "\n")
    sys.excepthook(exctype, value, tb)

sys.excepthook = exception_hook

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = load_config()

    window = MainWindow(config)
    window.show()

    tray = SystemTray(window, app)
    tray.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
