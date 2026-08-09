import os
import subprocess
import webbrowser
import datetime
import psutil
import re
import ctypes
from PIL import ImageGrab
import pyautogui
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL


class SystemActions:
    @staticmethod
    def lock_screen():
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Экран заблокирован"

    @staticmethod
    def sleep_mode():
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return "Перевожу компьютер в спящий режим"

    @staticmethod
    def shutdown_pc():
        os.system("shutdown /s /t 5")
        return "Выключаю ПК через пять секунд"

    @staticmethod
    def restart_pc():
        os.system("shutdown /r /t 5")
        return "Перезагружаю компьютер"

    @staticmethod
    def open_calculator():
        subprocess.Popen("calc.exe")
        return "Открываю калькулятор"

    @staticmethod
    def open_task_manager():
        subprocess.Popen("taskmgr.exe")
        return "Открываю диспетчер задач"

    @staticmethod
    def open_browser():
        webbrowser.open("https://google.com")
        return "Открываю браузер"

    @staticmethod
    def open_youtube():
        webbrowser.open("https://youtube.com")
        return "Открываю Ютуб"

    @staticmethod
    def open_yandex_music():
        webbrowser.open("https://music.yandex.ru")
        return "Открываю Яндекс Музыку"

    @staticmethod
    def open_spotify():
        subprocess.Popen(["cmd", "/c", "start", "spotify:"], shell=True)
        return "Запускаю Спотифай"

    @staticmethod
    def open_github():
        webbrowser.open("https://github.com")
        return "Открываю Гитхаб"

    @staticmethod
    def open_discord():
        subprocess.Popen(["cmd", "/c", "start", "discord:"], shell=True)
        return "Запускаю Дискорд"

    @staticmethod
    def open_telegram():
        subprocess.Popen(["cmd", "/c", "start", "telegram:"], shell=True)
        return "Запускаю Телеграм"

    @staticmethod
    def open_vpn():
        subprocess.Popen(["cmd", "/c", "start", "sota-vpn:"], shell=True)
        return "Запускаю Sota VPN"

    @staticmethod
    def open_media_player():
        subprocess.Popen("wmplayer.exe")
        return "Открываю медиаплеер"

    @staticmethod
    def take_screenshot():
        os.makedirs("screenshots", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = f"screenshots/screenshot_{timestamp}.png"
        img = ImageGrab.grab()
        img.save(path)
        return "Скриншот экрана сохранен"

    @staticmethod
    def volume_up(text=""):
        numbers = re.findall(r'\d+', text)
        steps = int(numbers[0]) if numbers else 5
        for _ in range(steps):
            pyautogui.press("volumeup")
        return f"Увеличиваю громкость"

    @staticmethod
    def volume_down(text=""):
        numbers = re.findall(r'\d+', text)
        steps = int(numbers[0]) if numbers else 5
        for _ in range(steps):
            pyautogui.press("volumedown")
        return f"Уменьшаю громкость"

    @staticmethod
    def set_volume(text=""):
        numbers = re.findall(r'\d+', text)
        if not numbers:
            return "Укажи уровень громкости от нуля до ста"
        level = max(0, min(100, int(numbers[0])))
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
        scalar = level / 100.0
        volume.SetMasterVolumeLevelScalar(scalar, None)
        return f"Громкость установлена на {level} процентов"

    @staticmethod
    def mute_volume():
        pyautogui.press("volumemute")
        return "Выключаю звук"

    @staticmethod
    def unmute_volume():
        pyautogui.press("volumeunmute")
        return "Включаю звук"

    @staticmethod
    def get_time():
        now = datetime.datetime.now()
        return f"Сейчас {now.strftime('%H:%M')}"

    @staticmethod
    def get_date():
        now = datetime.datetime.now()
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        return f"Сегодня {now.day} {months[now.month - 1]}"

    @staticmethod
    def get_system_stats():
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        return f"Загрузка процессора {cpu} процентов, оперативная память заполнена на {ram} процентов"