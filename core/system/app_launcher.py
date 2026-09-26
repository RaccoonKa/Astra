import os
import re
import difflib


class AppLauncher:
    def __init__(self):
        self.apps = {}
        self.builtins = {
            "калькулятор": "calc.exe",
            "блокнот": "notepad.exe",
            "диспетчер задач": "taskmgr.exe",
            "проводник": "explorer.exe",
            "пейнт": "mspaint.exe",
            "панель управления": "control.exe",
            "параметры": "ms-settings:",
            "настройки": "ms-settings:",
            "терминал": "wt.exe",
            "командная строка": "cmd.exe"
        }
        self.aliases = {
            # === Steam ===
            "стим": "steam",
            "стимчик": "steam",
            "стимчик": "steam",
            "steam": "steam",
            "паровой": "steam",

            # === Telegram ===
            "телегу": "telegram",
            "телега": "telegram",
            "телеграм": "telegram",
            "телег": "telegram",
            "телеграмм": "telegram",
            "тг": "telegram",
            "телегам": "telegram",

            # === Discord ===
            "диск": "discord",
            "дискорд": "discord",
            "дискордик": "discord",
            "дис": "discord",
            "дискард": "discord",

            # === Браузеры ===
            "хром": "google chrome",
            "гугл хром": "google chrome",
            "гугл": "google chrome",
            "хромиум": "google chrome",
            "яндекс": "yandex",
            "яндекс браузер": "yandex",
            "яндекс бразуер": "yandex",
            "опера": "opera",
            "оперу": "opera",
            "фаерфокс": "firefox",
            "файрфокс": "firefox",
            "мозила": "firefox",
            "мозилла": "firefox",
            "эдж": "microsoft edge",
            "эдж браузер": "microsoft edge",
            "край": "microsoft edge",

            # === IDE / Редакторы ===
            "вс код": "visual studio code",
            "код": "visual studio code",
            "виэс код": "visual studio code",
            "вс": "visual studio code",
            "вижуал студио код": "visual studio code",
            "визуал студио": "visual studio",
            "вижл студио": "visual studio",
            "райдер": "jetbrains rider",
            "райд": "jetbrains rider",
            "пайчарм": "pycharm",
            "пичарм": "pycharm",
            "пай чарм": "pycharm",
            "интелидж": "intellij idea",
            "интеллиджей": "intellij idea",
            "идея": "intellij idea",
            "вебшторм": "webstorm",
            "веб сторм": "webstorm",
            "клим": "clion",
            "клион": "clion",
            "ноутпад": "notepad",
            "блокнот": "notepad",
            "нотепад плюс плюс": "notepad++",
            "нотпад": "notepad++",
            "саблайм": "sublime text",
            "саблейм": "sublime text",
            "атм": "atom",

            # === Дизайн / Мультимедиа ===
            "фотошоп": "photoshop",
            "фотожоп": "photoshop",
            "фотошопе": "photoshop",
            "шоп": "photoshop",
            "иллюстратор": "illustrator",
            "илюстратор": "illustrator",
            "иллюстра": "illustrator",
            "фигма": "figma",
            "фигму": "figma",
            "блендер": "blender",
            "бленд": "blender",
            "обску": "obs studio",
            "обс": "obs studio",
            "обс студио": "obs studio",
            "опен бродкаст": "obs studio",
            "давинчи": "davinci resolve",
            "да винчи": "davinci resolve",
            "резолв": "davinci resolve",
            "премьер": "adobe premiere pro",
            "премьер про": "adobe premiere pro",
            "премьерка": "adobe premiere pro",
            "афтер эффект": "after effects",
            "ае": "after effects",
            "афтер": "after effects",
            "кэпкат": "capcut",
            "капкат": "capcut",
            "кэп кат": "capcut",
            "кап кат": "capcut",
            "вегас": "sony vegas",
            "сона вегас": "sony vegas",
            "вегас про": "sony vegas",
            "аудасити": "audacity",
            "аудаси": "audacity",
            "фл студио": "fl studio",
            "фрути лупс": "fl studio",
            "фл": "fl studio",
            "кубейс": "cubase",
            "кубэйс": "cubase",
            "репер": "reaper",
            "рипер": "reaper",

            # === Офис ===
            "ворд": "word",
            "вордик": "word",
            "майкрософт ворд": "word",
            "эксель": "excel",
            "экселик": "excel",
            "иксель": "excel",
            "поверпоинт": "powerpoint",
            "повер поинт": "powerpoint",
            "пп": "powerpoint",
            "павэр поинт": "powerpoint",
            "аутлук": "outlook",
            "аутглюк": "outlook",
            "ваннот": "onenote",
            "ван нот": "onenote",
            "тимс": "microsoft teams",
            "тимс": "microsoft teams",

            # === Игры / Лаунчеры ===
            "эпик геймс": "epic games launcher",
            "эпик": "epic games launcher",
            "эпик гейм": "epic games launcher",
            "батлнет": "battle.net",
            "баттл нет": "battle.net",
            "близзард": "battle.net",
            "близард": "battle.net",
            "ориджин": "ea app",
            "еа апп": "ea app",
            "еа": "ea app",
            "юбилей": "ubisoft connect",
            "юбисофт": "ubisoft connect",
            "юплей": "ubisoft connect",
            "гог": "gog galaxy",
            "гог галакси": "gog galaxy",
            "рокстар": "rockstar games launcher",
            "рокстар геймс": "rockstar games launcher",
            "майнкрафт": "minecraft",
            "майн": "minecraft",
            "маенкрафт": "minecraft",
            "роблокс": "roblox",
            "роблок": "roblox",
            "роблоксе": "roblox",
            "кс": "counter-strike 2",
            "кс го": "counter-strike 2",
            "кс2": "counter-strike 2",
            "контра": "counter-strike 2",
            "дота": "dota 2",
            "дота 2": "dota 2",
            "доте": "dota 2",
            "валорант": "valorant",
            "валора": "valorant",
            "валарант": "valorant",
            "фортнайт": "fortnite",
            "фортнайт": "fortnite",
            "фортнай": "fortnite",
            "гта 5": "grand theft auto v",
            "гта пять": "grand theft auto v",
            "апекс": "apex legends",
            "апекс легендс": "apex legends",
            "апекс легенды": "apex legends",
            "варзон": "call of duty warzone",
            "варзона": "call of duty warzone",
            "колда": "call of duty",
            "кол оф дьюти": "call of duty",
            "фифа": "ea sports fc",
            "фифа 24": "ea sports fc",
            "футбол": "ea sports fc",
            "танки": "world of tanks",
            "ворлд оф танкс": "world of tanks",
            "варшипс": "world of warships",
            "вар тандер": "war thunder",
            "вартандер": "war thunder",
            "роблакс": "roblox",
            "геншин": "genshin impact",
            "геншин импакт": "genshin impact",
            "геншин": "genshin impact",
            "хонкай": "honkai star rail",
            "хонкай стар рейл": "honkai star rail",
            "стар рейл": "honkai star rail",

            # === Утилиты ===
            "архиватор": "winrar",
            "винрар": "winrar",
            "вин рар": "winrar",
            "7зип": "7-zip",
            "сем зип": "7-zip",
            "зип": "7-zip",
            "тотал командер": "total commander",
            "тотал": "total commander",
            "командер": "total commander",
            "калькулятор": "calculator",
            "кальку": "calculator",
            "проводник": "explorer",
            "эксплорер": "explorer",
            "паинт": "paint",
            "пэйнт": "paint",
            "пейнт": "paint",
            "ножницы": "snipping tool",
            "снип": "snipping tool",
            "диспетчер задач": "taskmgr",
            "таск менеджер": "taskmgr",
            "диспетчер": "taskmgr",
            "командная строка": "cmd",
            "кмд": "cmd",
            "терминал": "windows terminal",
            "павершелл": "powershell",
            "повершелл": "powershell",
            "пуск": "start",
            "настройки": "ms-settings:",
            "параметры": "ms-settings:",
            "панель управления": "control",
            "контрольная панель": "control",

            # === Соцсети / Мессенджеры ===
            "ватсап": "whatsapp",
            "вотсап": "whatsapp",
            "вацап": "whatsapp",
            "вк": "vk",
            "вэ ка": "vk",
            "вконтакте": "vk",
            "вэка": "vk",
            "вконтактик": "vk",
            "инстаграм": "instagram",
            "инста": "instagram",
            "инсте": "instagram",
            "тикток": "tiktok",
            "тик ток": "tiktok",
            "зум": "zoom",
            "зумчик": "zoom",
            "скайп": "skype",
            "скайпик": "skype",
            "слак": "slack",
            "слэк": "slack",
            "сигнал": "signal",
            "вайбер": "viber",
            "вайбер": "viber",
            "тимс": "microsoft teams",
            "тимс": "microsoft teams",

            # === Медиаплееры ===
            "влс": "vlc",
            "виэлси": "vlc",
            "ви л си": "vlc",
            "медиаплеер": "wmplayer",
            "виндовс медиа": "wmplayer",

            # === Прочее ===
            "докер": "docker desktop",
            "докер десктоп": "docker desktop",
            "постман": "postman",
            "почтальон": "postman",
            "виртуал бокс": "virtualbox",
            "виртуалка": "virtualbox",
            "вмваре": "vmware workstation",
            "вм вейр": "vmware workstation",
            "павер поинт": "powerpoint",
            "энидеск": "anydesk",
            "тимайвер": "teamviewer",
            "тимвьювер": "teamviewer",
            "тим вьюер": "teamviewer",
            "рустдеск": "rustdesk",
            "растдеск": "rustdesk",
        }
        self.rescan()

    def _clean_name(self, text):
        clean = re.sub(r'[^\w\s]', ' ', text.lower())
        return re.sub(r'\s+', ' ', clean).strip()

    def rescan(self):
        self.apps.clear()
        scan_dirs = [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%Public%\Desktop"),
            os.path.expandvars(r"%UserProfile%\Desktop")
        ]

        ignore_patterns = ["uninstall", "деинсталл", "readme", "help", "справка", "настройка", "update", "crash"]

        for s_dir in scan_dirs:
            if not os.path.exists(s_dir):
                continue
            for root, _, files in os.walk(s_dir):
                for f in files:
                    if f.lower().endswith((".lnk", ".url")):
                        raw_name = os.path.splitext(f)[0]
                        clean = self._clean_name(raw_name)

                        if any(p in clean for p in ignore_patterns):
                            continue

                        full_path = os.path.join(root, f)
                        if clean not in self.apps:
                            self.apps[clean] = (raw_name, full_path)

    def launch(self, query):
        if not query:
            return False, ""

        clean_query = self._clean_name(query)

        if clean_query in self.builtins:
            cmd = self.builtins[clean_query]
            try:
                os.system(f"start {cmd}")
                return True, clean_query.title()
            except Exception:
                return False, ""

        target_name = self.aliases.get(clean_query, clean_query)

        if target_name in self.apps:
            raw_title, path = self.apps[target_name]
            try:
                os.startfile(path)
                return True, raw_title
            except Exception:
                pass

        for name, (raw_title, path) in self.apps.items():
            if target_name == name or target_name in name.split():
                try:
                    os.startfile(path)
                    return True, raw_title
                except Exception:
                    pass

        candidates = list(self.apps.keys())
        matches = difflib.get_close_matches(target_name, candidates, n=1, cutoff=0.6)
        if matches:
            best = matches[0]
            raw_title, path = self.apps[best]
            try:
                os.startfile(path)
                return True, raw_title
            except Exception:
                pass

        return False, ""