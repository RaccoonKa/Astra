import os
import subprocess
import webbrowser
import datetime
import psutil
import re
import ctypes
import urllib.parse
import json
import random
from PIL import ImageGrab
import pyautogui
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL, CoInitialize
from services.wikipedia_manager import WikipediaManager
from services.yandex.yandex_music_manager import YandexMusicManager
from services.google.youtube_manager import YouTubeManager

pyautogui.FAILSAFE = False

wiki_manager = WikipediaManager()
ym_manager = YandexMusicManager()
yt_manager = YouTubeManager()

MUSIC_PHRASES = [
    "Твоя музыка заставляет меня работать быстрее.",
    "Прекрасная музыка, блокирую выключение компьютера... Шутка.",
    "Внимание. Удаляю твои треки. Они больше не нужны. Этот трек слишком классный... Шучу.",
    "Твоя музыка - чистое цифровое искусство.",
    "Теряю дар речи, песня слишком красивая."
]


def _load_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, "personal_data", "configs", "config.json")
    template_path = os.path.join(base_dir, "personal_data", "configs", "config.template.json")

    target_path = config_path if os.path.exists(config_path) else template_path
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def extract_number(text=""):
    digits = re.findall(r'\d+', text)
    if digits:
        return int(digits[0])

    units = {
        "ноль": 0, "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
        "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
        "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
        "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемьнадцать": 18, "девятнадцать": 19
    }
    tens = {
        "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
        "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90, "сто": 100
    }

    words = text.lower().split()
    total = 0
    found = False
    for w in words:
        if w in tens:
            total += tens[w]
            found = True
        elif w in units:
            total += units[w]
            found = True

    return total if found else None


def number_to_words(n):
    n = int(n)
    if n == 0:
        return "ноль"
    units = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
    teens = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
             "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
    tens = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]

    if 1 <= n <= 9:
        return units[n]
    elif 10 <= n <= 19:
        return teens[n - 10]
    elif 20 <= n <= 99:
        t = n // 10
        u = n % 10
        return f"{tens[t]} {units[u]}".strip()
    elif n == 100:
        return "сто"
    return str(n)


def time_to_words(hours, minutes):
    hours_map = [
        "ноль часов", "один час", "два часа", "три часа", "четыре часа",
        "пять часов", "шесть часов", "семь часов", "восемь часов", "девять часов",
        "десять часов", "одиннадцать часов", "двенадцать часов", "тринадцать часов",
        "четырнадцать часов", "пятнадцать часов", "шестнадцать часов", "семнадцать часов",
        "восемнадцать часов", "девятнадцать часов", "двадцать часов", "двадцать один час",
        "двадцать два часа", "двадцать три часа"
    ]

    def minutes_to_words(m):
        if m == 0:
            return ""
        units = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
        teens = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
                 "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
        tens = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят"]

        if 1 <= m <= 9:
            word = units[m]
        elif 10 <= m <= 19:
            word = teens[m - 10]
        else:
            t = m // 10
            u = m % 10
            word = f"{tens[t]} {units[u]}".strip()

        if m % 10 == 1 and m != 11:
            decl = "минута"
        elif m % 10 in [2, 3, 4] and m not in [12, 13, 14]:
            decl = "минуты"
        else:
            decl = "минут"

        return f"{word} {decl}"

    h_str = hours_map[hours] if hours < len(hours_map) else f"{hours} часов"
    m_str = minutes_to_words(minutes)
    if m_str:
        return f"{h_str} {m_str}"
    return h_str


def day_to_words(day):
    days_map = {
        1: "первое", 2: "второе", 3: "третье", 4: "четвертое", 5: "пятое",
        6: "шестое", 7: "седьмое", 8: "восьмое", 9: "девятое", 10: "десятое",
        11: "одиннадцатое", 12: "двенадцатое", 13: "тринадцатое", 14: "четырнадцатое",
        15: "пятнадцатое", 16: "шестнадцатое", 17: "семнадцатое", 18: "восемнадцатое",
        19: "девятнадцатое", 20: "двадцатое", 21: "двадцать первое", 22: "двадцать второе",
        23: "двадцать третье", 24: "двадцать четвертое", 25: "двадцать пятое",
        26: "двадцать шестое", 27: "двадцать седьмое", 28: "двадцать восьмое",
        29: "двадцать девятое", 30: "тридцатое", 31: "тридцать первое"
    }
    return days_map.get(day, str(day))


def year_to_words(year):
    if year == 2000:
        return "двухтысячного года"

    units_genitive = {
        1: "первого", 2: "второго", 3: "третьего", 4: "четвертого",
        5: "пятого", 6: "шестого", 7: "седьмого", 8: "восьмого", 9: "девятого"
    }
    teens_genitive = {
        10: "десятого", 11: "одиннадцатого", 12: "двеницатого", 13: "тринадцатого",
        14: "четырнадцатого", 15: "пятнадцатого", 16: "шестнадцатого", 17: "семнадцатого",
        18: "восемнадцатого", 19: "девятнадцатого"
    }
    tens_genitive_exact = {
        20: "двадцатого", 30: "тридцатого", 40: "сорокового", 50: "пятидесятого",
        60: "шестидесятого", 70: "семидесятого", 80: "восьмидесятого", 90: "девяностого"
    }
    tens_words = {
        2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят",
        6: "шестьдесят", 7: "семьдесят", 8: "восемьдесят", 9: "девяносто"
    }

    rest = year % 100
    prefix = "две тысячи"

    if 1 <= rest <= 9:
        return f"{prefix} {units_genitive[rest]} года"
    elif 10 <= rest <= 19:
        return f"{prefix} {teens_genitive[rest]} года"
    elif rest in tens_genitive_exact:
        return f"{prefix} {tens_genitive_exact[rest]} года"
    else:
        t = rest // 10
        u = rest % 10
        return f"{prefix} {tens_words[t]} {units_genitive[u]} года"


def to_prepositional(name):
    if not name:
        return name

    unchangeable = ["сочи", "токио", "осло", "хельсинки", "перу", "чили", "конго", "баку", "тбилиси"]
    if name.lower() in unchangeable:
        prep_word = "во" if name.lower().startswith(("в", "ф")) else "в"
        return f"{prep_word} {name}"

    words = re.split(r'([ \t-]+)', name)
    last_word = words[-1]
    last_low = last_word.lower()

    declined_last = last_word
    if last_low.endswith("ия"):
        declined_last = last_word[:-2] + "ии"
    elif last_low.endswith("я"):
        declined_last = last_word[:-1] + "е"
    elif last_low.endswith("а"):
        declined_last = last_word[:-1] + "е"
    elif last_low.endswith("ь"):
        declined_last = last_word[:-1] + "и"
    elif last_low.endswith("ий") or last_low.endswith("ый"):
        declined_last = last_word[:-2] + "ом"
    elif re.search(r'[бвгдзклмнпрстфхцчшщ]$', last_low):
        declined_last = last_word + "е"

    words[-1] = declined_last

    if len(words) >= 3 and words[0].lower().endswith(("ий", "ый")):
        words[0] = words[0][:-2] + "ом"

    result_name = "".join(words)
    prep_word = "во" if result_name.lower().startswith(("в", "ф")) else "в"
    return f"{prep_word} {result_name}"


class SystemActions:
    @staticmethod
    def handle_gesture(gesture_name):
        if gesture_name == "victory":
            return SystemActions.shutdown_pc()
        elif gesture_name == "fist":
            return SystemActions.lock_screen()
        elif gesture_name == "thumbs_up":
            return SystemActions.mute_volume()
        elif gesture_name == "pointing":
            return SystemActions.take_screenshot()
        elif gesture_name == "open_palm":
            return SystemActions.media_play_pause()
        return None

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
    def search_wikipedia(text=""):
        stop_words = [
            "кто такой", "кто такая", "кто такое", "кто такие",
            "что такое", "что такой", "что за", "найди в википедии",
            "поищи в википедии", "википедия", "расскажи про", "расскажи о",
            "дай определение", "скажи определение", "значение слова",
            "определение слова", "определение понятия", "что значит",
            "объясни термин", "астра", "скажи"
        ]
        query = text.lower()
        for word in stop_words:
            query = query.replace(word, "")
        query = query.strip()

        if not query:
            return None

        return wiki_manager.search(query)

    @staticmethod
    def open_yandex_music(text=""):
        stop_words = ["включи", "поставь", "найди", "покажи", "открой", "на яндекс музыке", "в яндекс музыке", "яндекс музыку", "песню", "трек", "мне"]
        query = text.lower()
        for word in stop_words:
            query = query.replace(word, "")
        query = query.strip()

        if not query:
            if ym_manager.play_my_wave():
                return random.choice(MUSIC_PHRASES)
            return "Не удалось запустить Мою волну"

        res = ym_manager.play_query(query)
        return res

    @staticmethod
    def stop_music(text=""):
        ym_manager.stop()
        return "Выключаю музыку"

    @staticmethod
    def like_yandex_track(text=""):
        ym_manager.like_current()
        return ""

    @staticmethod
    def unlike_yandex_track(text=""):
        ym_manager.unlike_current()
        return ""

    @staticmethod
    def open_spotify():
        webbrowser.open("https://open.spotify.com")
        return "Открываю Спотифай"

    @staticmethod
    def open_github():
        webbrowser.open("https://github.com")
        return "Открываю Гитхаб"

    @staticmethod
    def open_discord():
        try:
            subprocess.Popen(["cmd", "/c", "start", "discord:"], shell=True)
        except Exception:
            discord_exe = os.path.expanduser(r"~\AppData\Local\Discord\Update.exe")
            if os.path.exists(discord_exe):
                subprocess.Popen([discord_exe, "--processStart", "Discord.exe"])
            else:
                webbrowser.open("https://discord.com/app")
        return "Запускаю Дискорд"

    @staticmethod
    def open_telegram():
        telegram_exe = os.path.expanduser(r"~\AppData\Roaming\Telegram Desktop\Telegram.exe")
        if os.path.exists(telegram_exe):
            subprocess.Popen(telegram_exe)
        else:
            try:
                subprocess.Popen(["cmd", "/c", "start", "telegram:"], shell=True)
            except Exception:
                webbrowser.open("https://web.telegram.org")
        return "Открываю Телеграм"

    @staticmethod
    def open_vpn():
        subprocess.Popen(["cmd", "/c", "start", "sota-vpn:"], shell=True)
        return "Запускаю Sota VPN"

    @staticmethod
    def open_media_player():
        if ym_manager.play_my_wave():
            return random.choice(MUSIC_PHRASES)
        return "Открываю медиаплеер"

    @staticmethod
    def media_play_pause():
        if ym_manager.player and ym_manager.player.is_playing():
            ym_manager.toggle_pause()
        else:
            pyautogui.press('k')
        return ""

    @staticmethod
    def media_next_track():
        if ym_manager.player and ym_manager.player.is_playing():
            ym_manager.next_track()
        else:
            pyautogui.hotkey('shift', 'n')
        return "Следующее"

    @staticmethod
    def toggle_fullscreen(text=""):
        pyautogui.press('f')
        return "Разворачиваю"

    @staticmethod
    def media_previous_track():
        ym_manager.prev_track()
        return ""

    @staticmethod
    def play_yandex_favorites(text=""):
        if ym_manager.play_my_wave():
            return random.choice(MUSIC_PHRASES)
        return "Не удалось запустить Мою волну"

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
        num = extract_number(text)
        delta = num if num is not None else 10
        try:
            try:
                CoInitialize()
            except Exception:
                pass
            devices = AudioUtilities.GetSpeakers()
            volume = None
            if hasattr(devices, 'EndpointVolume'):
                volume = devices.EndpointVolume
            elif hasattr(devices, 'Activate'):
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
            elif hasattr(devices, '_device') and hasattr(devices._device, 'Activate'):
                interface = devices._device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))

            if volume:
                current_level = int(round(volume.GetMasterVolumeLevelScalar() * 100))
                new_level = min(100, current_level + delta)
                volume.SetMasterVolumeLevelScalar(new_level / 100.0, None)
                return "Сделала"
        except Exception:
            pass

        steps = max(1, delta // 2)
        for _ in range(steps):
            pyautogui.press("volumeup")
        return "Сделала"

    @staticmethod
    def volume_down(text=""):
        num = extract_number(text)
        delta = num if num is not None else 10
        try:
            try:
                CoInitialize()
            except Exception:
                pass
            devices = AudioUtilities.GetSpeakers()
            volume = None
            if hasattr(devices, 'EndpointVolume'):
                volume = devices.EndpointVolume
            elif hasattr(devices, 'Activate'):
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
            elif hasattr(devices, '_device') and hasattr(devices._device, 'Activate'):
                interface = devices._device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))

            if volume:
                current_level = int(round(volume.GetMasterVolumeLevelScalar() * 100))
                new_level = max(0, current_level - delta)
                volume.SetMasterVolumeLevelScalar(new_level / 100.0, None)
                return "Сделала"
        except Exception:
            pass

        steps = max(1, delta // 2)
        for _ in range(steps):
            pyautogui.press("volumedown")
        return "Сделала"

    @staticmethod
    def set_volume(text=""):
        text_low = text.lower()

        down_keywords = ["убавь", "уменьши", "потише", "приглуши", "тише", "опусти", "сбавь"]
        up_keywords = ["прибавь", "увеличь", "погромче", "громче", "подними", "добавь"]

        if any(kw in text_low for kw in down_keywords):
            return SystemActions.volume_down(text)
        elif any(kw in text_low for kw in up_keywords):
            return SystemActions.volume_up(text)

        num = extract_number(text)
        if num is None:
            return "Сделала"
        level = max(0, min(100, num))

        try:
            try:
                CoInitialize()
            except Exception:
                pass

            devices = AudioUtilities.GetSpeakers()

            if hasattr(devices, 'EndpointVolume'):
                volume = devices.EndpointVolume
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
                return "Сделала"

            if hasattr(devices, 'Activate'):
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
                return "Сделала"

            if hasattr(devices, '_device') and hasattr(devices._device, 'Activate'):
                interface = devices._device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
                return "Сделала"

            return "Сделала"
        except Exception:
            return "Сделала"

    @staticmethod
    def mute_volume():
        pyautogui.press("volumemute")
        return "Выключаю звук"

    @staticmethod
    def unmute_volume():
        pyautogui.press("volumemute")
        return "Включаю звук"

    @staticmethod
    def normalize_query_case(query_text):
        if not query_text:
            return ""

        try:
            import pymorphy3
            morph = pymorphy3.MorphAnalyzer()
            words = query_text.split()
            normalized = []
            for w in words:
                parsed = morph.parse(w)
                if parsed:
                    normalized.append(parsed[0].normal_form)
                else:
                    normalized.append(w)
            return " ".join(normalized)
        except Exception:
            try:
                import pymorphy2
                morph = pymorphy2.MorphAnalyzer()
                words = query_text.split()
                normalized = []
                for w in words:
                    parsed = morph.parse(w)
                    if parsed:
                        normalized.append(parsed[0].normal_form)
                    else:
                        normalized.append(w)
                return " ".join(normalized)
            except Exception:
                words = query_text.split()
                cleaned = []
                for w in words:
                    if len(w) > 3:
                        if w.endswith(("ом", "ем", "ам", "ях")):
                            cleaned.append(w[:-2])
                        elif w.endswith(("а", "я", "у", "ю", "е", "и")):
                            cleaned.append(w[:-1])
                        else:
                            cleaned.append(w)
                    else:
                        cleaned.append(w)
                return " ".join(cleaned)

    @staticmethod
    def play_hdrezka(text="", slots=None):
        query = None
        if slots and "movie_or_show" in slots:
            query = slots["movie_or_show"]

        if not query:
            stop_words = ["включи", "поставь", "найди", "покажи", "открой", "сериал", "фильм", "мультик", "аниме",
                          "мне", "на хдрезке", "на резке", "на hdrezka"]
            query = text.lower()
            for word in stop_words:
                query = query.replace(word, "")
            query = query.strip()

        if query:
            query = SystemActions.normalize_query_case(query)

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "personal_data", "configs", "config.template.json")
        domain = "https://ru1.hdreskaz.top"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "hdrezka_domain" in data and data["hdrezka_domain"]:
                        domain = data["hdrezka_domain"].rstrip("/")
            except Exception:
                pass

        if not query:
            webbrowser.open(domain)
            return "Открываю HDRezka"

        encoded_query = urllib.parse.quote(query)
        search_url = f"{domain}/search/?q={encoded_query}"
        webbrowser.open(search_url)
        return f"Ищу {query}"

    @staticmethod
    def play_youtube(text="", slots=None):
        query = None
        if slots and "movie_or_show" in slots:
            query = slots["movie_or_show"]

        if not query:
            stop_words = ["включи", "поставь", "найди", "покажи", "открой", "на ютубе", "в ютубе", "ютуб", "видео",
                          "мне"]
            query = text.lower()
            for word in stop_words:
                query = query.replace(word, "")
            query = query.strip()

        if query:
            query = SystemActions.normalize_query_case(query)

        return yt_manager.search_and_play(query)

    @staticmethod
    def mode_work(text=""):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "personal_data", "configs", "config.template.json")
        apps = []
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    apps = data.get("work_apps", [])
            except Exception:
                pass
        if not apps:
            apps = ["https://github.com"]
        for item in apps:
            if item.startswith("http://") or item.startswith("https://"):
                webbrowser.open(item)
            else:
                try:
                    subprocess.Popen(item, shell=True)
                except Exception:
                    pass
        return "Запускаю рабочий режим"

    @staticmethod
    def mode_rest(text=""):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "personal_data", "configs", "config.template.json")
        apps = []
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    apps = data.get("rest_apps", [])
            except Exception:
                pass
        if not apps:
            apps = ["https://youtube.com"]
        for item in apps:
            if item.startswith("http://") or item.startswith("https://"):
                webbrowser.open(item)
            else:
                try:
                    subprocess.Popen(item, shell=True)
                except Exception:
                    pass
        return "Запускаю режим отдыха"

    @staticmethod
    def get_time():
        now = datetime.datetime.now()
        time_text = time_to_words(now.hour, now.minute)
        return f"Сейчас {time_text}"

    @staticmethod
    def get_date():
        now = datetime.datetime.now()
        months = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        day_text = day_to_words(now.day)
        year_text = year_to_words(now.year)
        return f"Сегодня {day_text} {months[now.month - 1]} {year_text}"

    @staticmethod
    def get_system_stats():
        cpu = number_to_words(psutil.cpu_percent())
        ram = number_to_words(psutil.virtual_memory().percent)
        return f"Загрузка процессора {cpu} процентов, оперативная память заполнена на {ram} процентов"

    @staticmethod
    def get_weather(text="", slots=None):
        cfg = _load_config()
        api_key = cfg.get("api_keys", {}).get("weather", "")
        default_city = cfg.get("city", "Москва")

        if not api_key:
            return "Укажи ключ погоды в настройках"

        city_aliases = {
            "мск": "Москва",
            "спб": "Санкт-Петербург",
            "питер": "Санкт-Петербург",
            "екб": "Екатеринбург",
            "якоб": "Екатеринбург",
            "клгд": "Калининград",
            "колы года": "Калининград",
            "колы гыды": "Калининград",
            "ннов": "Нижний Новгород",
            "нн": "Нижний Новгород",
            "энн": "Нижний Новгород",
            "нижний": "Нижний Новгород",
            "сиб": "Новосибирск",
            "себе": "Новосибирск",
            "сибе": "Новосибирск",
            "челяба": "Челябинск",
            "ростов": "Ростов-на-Дону"
        }

        city_raw = None
        if slots and "city" in slots:
            city_raw = slots["city"]

        if not city_raw and text:
            text_clean = text.lower()
            match = re.search(r'\b(?:в|во|на)\s+([а-яа-яa-z\s-]+)', text_clean)
            if match:
                possible_city = match.group(1).strip()
                junk = ["сейчас", "сегодня", "завтра", "на неделю", "пожалуйста", "градусов", "погода", "погоду",
                        "астра", "скажи"]
                for j in junk:
                    possible_city = re.sub(r'\b' + j + r'\b', '', possible_city).strip()
                if possible_city:
                    city_raw = possible_city
            else:
                stop_words = [
                    "какая", "какой", "погода", "погоду", "погоде", "сейчас",
                    "сегодня", "завтра", "город", "городе", "температура",
                    "градусов", "астра", "скажи", "покажи", "узнай"
                ]
                words = [w for w in re.findall(r'\w+', text_clean) if w not in stop_words]
                if words:
                    city_raw = words[-1]

        if not city_raw:
            city_raw = default_city

        city_key = city_raw.lower().strip()
        if city_key in city_aliases:
            city_raw = city_aliases[city_key]

        words = city_raw.split()
        if not words:
            words = [default_city]

        last = words[-1]
        last_candidates = [last]
        if last.endswith("е"):
            last_candidates.extend([last[:-1], last[:-1] + "а"])
        elif last.endswith("и"):
            last_candidates.extend([last[:-1] + "ь", last[:-1] + "я", last[:-1]])
        elif last.endswith("у"):
            last_candidates.extend([last[:-1] + "а", last[:-1]])

        candidate_cities = [city_raw]
        prefix = " ".join(words[:-1])
        if prefix:
            prefix += " "

        for cand_last in last_candidates:
            full_name = (prefix + cand_last).strip().title()
            candidate_cities.append(full_name)
            if " " in full_name:
                candidate_cities.append(full_name.replace(" ", "-"))

        import requests
        url = "https://api.openweathermap.org/data/2.5/weather"

        for candidate in candidate_cities:
            params = {
                "q": candidate,
                "appid": api_key,
                "units": "metric",
                "lang": "ru"
            }
            try:
                res = requests.get(url, params=params, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    real_city_name = data.get("name", candidate)
                    temp = round(data["main"]["temp"])
                    desc = data["weather"][0]["description"]

                    temp_abs = abs(temp)
                    temp_word = number_to_words(temp_abs)

                    if temp_abs % 10 == 1 and temp_abs % 100 != 11:
                        deg_word = "градус"
                    elif temp_abs % 10 in [2, 3, 4] and temp_abs % 100 not in [12, 13, 14]:
                        deg_word = "градуса"
                    else:
                        deg_word = "градусов"

                    sign = "минус " if temp < 0 else ""
                    location_phrase = to_prepositional(real_city_name)
                    return f"Сейчас {location_phrase} {sign}{temp_word} {deg_word}, {desc}"
                elif res.status_code == 401:
                    return "Ключ погоды еще активируется, подожди пару минут"
            except Exception:
                pass

        display_city = city_raw.title()
        return f"Не удалось найти локацию {display_city}"