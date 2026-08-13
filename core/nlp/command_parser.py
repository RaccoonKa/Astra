import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import re
import threading
from transformers.utils import logging as tf_logging
from core.system.actions import SystemActions
from core.nlp.llm_provider import GigaChatProvider
from core.nlp.nlu import JointNLU

tf_logging.set_verbosity_error()


class CommandParser:
    def __init__(self, confidence_threshold=0.60):
        self.threshold = confidence_threshold
        self.llm = GigaChatProvider()

        self.intent_aliases = {
            "search_video": "play_youtube",
            "shutdown": "shutdown_pc"
        }

        self.nlu = None
        self.is_ready = False

        self.loader_thread = threading.Thread(target=self._load_model, daemon=True)
        self.loader_thread.start()

    def _load_model(self):
        try:
            self.nlu = JointNLU(model_dir="models/joint_nlu")
        except Exception as e:
            print(f"[PARSER ERROR]: Не удалось загрузить JointNLU: {e}")

        self.is_ready = True

    def _check_rules(self, text):
        text_low = text.lower()
        words = set(re.findall(r'\w+', text_low))

        media_stop_phrases = [
            "выключи музыку", "выключи трек", "выключи музло", "выключи песню",
            "останови музыку", "стоп музыка", "заглуши музыку", "выключи плеер"
        ]
        for msp in media_stop_phrases:
            if msp in text_low:
                return "stop_music"

        fullscreen_keywords = [
            "разверни", "на весь экран", "во весь экран", "полный экран",
            "разверни видео", "на полный экран", "развернуть"
        ]
        for kw in fullscreen_keywords:
            if kw in text_low:
                return "toggle_fullscreen"

        if len(words) > 7:
            strict_command_roots = [
                "выключ", "перезагруз", "погод", "градус", "громкост",
                "потише", "погромче", "скрин", "залочь", "заблокируй"
            ]
            if not any(root in text_low for root in strict_command_roots):
                return "chat"

        if "как" in text_low and any(w in text_low for w in ["дел", "жизн", "оно", "делишк", "пожива"]):
            return "chat"

        chat_phrases = [
            "чем занимаешься", "что делаешь", "что нового", "расскажи что нибудь",
            "ты лучшая", "ты супер", "молодец", "красотка", "спасибо",
            "благодарю", "люблю тебя", "я тебя люблю", "тебя люблю", "обожаю тебя",
            "поженимся", "выйди за меня", "поцелуй", "женись", "свадьба",
            "ты классная", "отлично", "круто", "поболтаем", "поговорим",
            "привет", "хай", "здравствуй", "кто ты", "как тебя зовут",
            "все хорошо", "всё хорошо", "все отлично", "всё отлично", "все супер",
            "нормально", "все норм", "всё норм", "тоже хорошо", "тоже нормально",
            "да так", "ничего особого", "потихоньку", "хорошо", "да пойдет",
            "не жалуюсь", "норм", "ок", "все ок", "всё ок",
            "еще", "ещё", "давай еще", "давай ещё", "еще один", "ещё один",
            "давай еще один", "давай ещё один", "расскажи еще", "расскажи ещё",
            "давай другой", "давай еще анекдот", "давай ещё анекдот"
        ]
        for cp in chat_phrases:
            if cp in text_low:
                return "chat"

        chat_roots = ["пожен", "жениз", "замуж", "целу", "обним", "свадьб", "нравиш"]
        if any(root in text_low for root in chat_roots):
            return "chat"

        volume_roots = ["громк", "громок", "звук", "потише", "погромче", "убавь", "прибавь", "волюм"]
        if any(root in text_low for root in volume_roots):
            return "set_volume"

        my_wave_triggers = [
            "волн", "валн", "мои ладно", "мою ладно", "моя ладно",
            "мою главного", "моя главная", "свою волн", "своя волн",
            "любимо", "любиму", "мне нравит", "понравивш", "мои треки"
        ]
        if any(trig in text_low for trig in my_wave_triggers):
            return "play_yandex_favorites"

        unlike_keywords = ["убери лайк", "удали лайк", "дизлайк", "дизлайкни", "убери из любимого", "удали из любимого",
                           "сними лайк"]
        for kw in unlike_keywords:
            if kw in text_low:
                return "unlike_yandex_track"

        like_keywords = ["добавь в любимое", "добавь в избранное", "поставь лайк", "лайкни песню", "лайкни трек",
                         "поставишь лайк", "лайк"]
        for kw in like_keywords:
            if kw in text_low:
                return "like_yandex_track"

        play_pause_keywords = [
            "пауза", "паузу", "продолжи", "играй", "запускай", "включай",
            "стоп трек", "поставь на паузу", "сними с паузы", "возобнови"
        ]

        next_track_keywords = [
            "следующий трек", "следующая песня", "следующее видео", "следующий ролик",
            "следующий", "следующее", "следующая", "следующую",
            "дальше", "переключи трек", "переключи видео", "переключи", "след", "вперед", "вперёд"
        ]

        prev_track_keywords = [
            "предыдущий трек", "предыдущая песня", "предыдущий", "предыдущее", "предыдущая", "предыдущую",
            "назад трек", "верни трек", "назад", "прошлый", "прошлая", "прошлое", "пред"
        ]

        for kw in play_pause_keywords:
            if kw in text_low:
                return "media_play_pause"

        for kw in next_track_keywords:
            if kw in text_low or any(w.startswith("след") for w in words):
                return "media_next_track"

        for kw in prev_track_keywords:
            if kw in text_low or any(w.startswith("пред") for w in words):
                return "media_previous_track"

        wiki_triggers = [
            "википед", "вики", "кто так", "кто таков", "что так", "что за",
            "расскажи про", "расскажи о", "дай определение", "скажи определение",
            "определение слова", "определение понятия", "значение слова",
            "что значит", "объясни термин"
        ]
        if any(trig in text_low for trig in wiki_triggers):
            return "search_wikipedia"

        return None

    def process_command(self, text):
        if not text:
            return ""

        rule_intent = self._check_rules(text)
        if rule_intent == "chat":
            print(f"[PARSER]: Услышано '{text}' -> Разговорное правило -> GigaChat")
            return self.llm.ask(text)

        if not self.is_ready:
            self.loader_thread.join()

        intent = None
        slots = {}

        if rule_intent:
            intent = rule_intent
            print(f"[PARSER]: Услышано '{text}' -> Правило: {intent}")
            if self.nlu:
                _, _, slots = self.nlu.predict(text)
        else:
            if self.nlu:
                intent, confidence, slots = self.nlu.predict(text)
                print(f"[PARSER]: Услышано '{text}' -> JointNLU: {intent} ({int(confidence * 100)}%)")
                if confidence < self.threshold:
                    intent = None

        if intent in ["shutdown", "shutdown_pc"]:
            media_guard = ["музык", "трек", "песн", "музл", "звук", "плеер", "видос", "видео"]
            if any(mg in text.lower() for mg in media_guard):
                print(f"[SAFETY]: Заблокирован shutdown для медиа-запроса '{text}' -> Остановка плеера")
                return SystemActions.stop_music()

            shutdown_keywords = ["выключ", "перезагруз", "выруб", "отключ", "шатдаун", "reboot", "спать", "заверш",
                                 "рестарт"]
            if not any(kw in text.lower() for kw in shutdown_keywords):
                print(f"[SAFETY]: Заблокирован ложный shutdown для '{text}' -> Запрос отправлен в GigaChat")
                return self.llm.ask(text)

        if slots:
            print(f"[SLOT FILLER]: Выделены сущности -> {slots}")

        if intent:
            action_name = self.intent_aliases.get(intent, intent)
            action_func = getattr(SystemActions, action_name, None)
            if action_func is not None:
                try:
                    res = action_func(text, slots=slots)
                except TypeError:
                    try:
                        res = action_func(text)
                    except TypeError:
                        res = action_func()

                if res is not None:
                    return res

        print(f"[PARSER]: Передаем запрос в GigaChat -> '{text}'")
        return self.llm.ask(text)