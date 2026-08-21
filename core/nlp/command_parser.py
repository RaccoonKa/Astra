import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import re
import threading
from transformers.utils import logging as tf_logging
from core.system.actions import SystemActions, zapret_manager
from services.vpn.vpn_manager import VpnManager
from core.nlp.llm_provider import GigaChatProvider
from core.nlp.nlu import JointNLU
from core.nlp.emotion_classifier import EmotionClassifier, EMOTION_TRANSLATION
from core.nlp.document_parser import DocumentParser
from services.telegram.user_client import TelegramUserManager

tf_logging.set_verbosity_error()

vpn_manager = VpnManager()

WORD_TO_NUM = {
    "один": 1, "первый": 1, "первую": 1, "первое": 1, "первой": 1,
    "два": 2, "второй": 2, "вторую": 2, "второе": 2, "второй": 2,
    "три": 3, "третий": 3, "третью": 3, "третье": 3,
    "четыре": 4, "четвертый": 4, "четвертую": 4, "четвертое": 4, "четвёртый": 4, "четвёртую": 4, "четвёртое": 4,
    "пять": 5, "пятый": 5, "пятую": 5, "пятое": 5,
    "шесть": 6, "шестой": 6, "шестую": 6, "шестое": 6,
    "семь": 7, "седьмой": 7, "седьмую": 7, "седьмое": 7,
    "восемь": 8, "восьмой": 8, "восьмую": 8, "восьмое": 8,
    "девять": 9, "девятый": 9, "девятую": 9, "девятое": 9,
    "десять": 10, "десятый": 10, "десятую": 10, "десятое": 10,
    "одиннадцать": 11, "одиннадцатый": 11, "одиннадцатую": 11, "одиннадцатое": 11,
    "двенадцать": 12, "двенадцатый": 12, "двенадцатую": 12, "двенадцатое": 12,
    "тринадцать": 13, "тринадцатый": 13, "тринадцатую": 13, "тринадцатое": 13,
    "четырнадцать": 14, "четырнадцатый": 14, "четырнадцатую": 14, "четырнадцатое": 14,
    "пятнадцать": 15, "пятнадцатый": 15, "пятнадцатую": 15, "пятнадцатое": 15,
    "шестнадцать": 16, "шестнадцатый": 16, "шестнадцатую": 16, "шестнадцатое": 16,
    "семнадцать": 17, "семнадцатый": 17, "семнадцатую": 17, "семнадцатое": 17,
    "восемнадцать": 18, "восемнадцатый": 18, "восемнадцатую": 18, "восемнадцатое": 18,
    "девятнадцать": 19, "девятнадцатый": 19, "девятнадцатую": 19, "девятнадцатое": 19,
    "двадцать": 20, "двадцатый": 20, "двадцатую": 20, "двадцатое": 20
}


class CommandParser:
    def __init__(self, confidence_threshold=0.60):
        self.threshold = confidence_threshold
        self.llm = GigaChatProvider()
        self.emotion_classifier = EmotionClassifier()
        self.doc_parser = DocumentParser()
        self.waiting_for_zapret = False
        self.waiting_for_vpn = False
        self.last_emotion = "neutral"

        self.intent_aliases = {
            "play_music": "play_music",
            "search_video": "play_youtube",
            "shutdown": "shutdown_pc",
            "start_zapret": "start_zapret",
            "stop_zapret": "stop_zapret",
            "mode_work": "mode_work",
            "mode_rest": "mode_rest",
            "start_vpn": "start_vpn",
            "stop_vpn": "stop_vpn"
        }

        self.nlu = None
        self.is_ready = False

        self.loader_thread = threading.Thread(target=self._load_model, daemon=True)
        self.loader_thread.start()

        self.tg_user_mgr = TelegramUserManager()
        self.waiting_for_tg_msg = False
        self.tg_recipient = None

    def _load_model(self):
        try:
            self.nlu = JointNLU(model_dir="optimized_models/joint_nlu")
        except Exception as e:
            print(f"[PARSER ERROR]: Не удалось загрузить JointNLU: {e}")

        self.is_ready = True

    def _extract_zapret_number(self, text):
        text_clean = text.lower().strip()
        match = re.search(r'\b([1-9]|1[0-9]|20)\b', text_clean)
        if match:
            return int(match.group(1))
        for word, num in WORD_TO_NUM.items():
            if re.search(r'\b' + word + r'\b', text_clean):
                return num
        return None

    def _check_rules(self, text):
        text_low = text.lower().strip()
        words = set(re.findall(r'\w+', text_low))

        if text_low in ["работа", "отдых"]:
            return "mode_work" if text_low == "работа" else "mode_rest"

        work_triggers = [
            "рабочий режим", "режим работы", "режим работа", "включи работу", "запусти работу",
            "пора работать", "время работать", "начать работу", "начни работу", "включи рабочий режим",
            "запусти рабочий режим", "открой работу", "вруби работу"
        ]
        for wt in work_triggers:
            if wt in text_low:
                return "mode_work"

        rest_triggers = [
            "режим отдыха", "режим отдых", "включи отдых", "запусти отдых",
            "пора отдыхать", "время отдыхать", "хочу отдохнуть", "давай отдохнем",
            "давай отдохнём", "включи режим отдыха", "запусти режим отдыха",
            "открой отдых", "вруби отдых"
        ]
        for rt in rest_triggers:
            if rt in text_low:
                return "mode_rest"

        has_generic_vpn = vpn_manager.is_generic_vpn_mention(text_low)
        parsed_vpn = vpn_manager.parse_vpn_name(text_low)

        if has_generic_vpn or parsed_vpn != "none":
            stop_verbs = ["выключ", "отключ", "выруб", "останов", "заглуш", "погас", "стоп", "закрой"]
            start_verbs = ["включ", "запуст", "вруб", "подключ", "открой", "активир", "стартуй", "подруби", "поставь"]

            if any(sv in text_low for sv in stop_verbs):
                return "stop_vpn"
            if any(sv in text_low for sv in start_verbs) or has_generic_vpn or parsed_vpn != "none":
                return "start_vpn"

        shutdown_triggers = [
            "выключи компьютер", "выключи пк", "выруби компьютер", "выруби пк", "выруби комп",
            "выключи комп", "выключай пк", "выключай компьютер", "выключай комп",
            "спокойной ночи", "доброй ночи", "до завтра", "до свидания", "до встречи",
            "вырубай компьютер", "вырубай пк", "вырубай комп", "заверши работу", "заверши работу пк",
            "завершить работу", "заверши сеанс", "гаси комп", "гаси пк", "туши свет", "бай бай"
        ]
        for st in shutdown_triggers:
            if st in text_low:
                return "shutdown"

        if re.search(r'\b(?:пока|бай-бай|до скорого)\b', text_low):
            if not any(w in text_low for w in ["покажи", "покатай", "пока что", "покажи-ка", "покажите"]):
                return "shutdown"

        zapret_stop_phrases = [
            "выключи запрет", "останови запрет", "выруби запрет", "заглуши запрет",
            "выключи обход", "останови обход", "выключи обход блокировок", "выруби обход",
            "выключи winws", "останови winws", "выключи zapret", "останови zapret"
        ]
        for zsp in zapret_stop_phrases:
            if zsp in text_low:
                return "stop_zapret"

        zapret_menu_triggers = [
            "включи запрет", "запусти запрет", "вруби запрет", "открой запрет",
            "включи обход", "запусти обход", "включи обход блокировок", "вруби обход",
            "включи winws", "запусти winws", "включи zapret", "запусти zapret",
            "смени обход", "поменяй обход", "выбери обход", "список обходов",
            "какой обход", "какие обходы", "покажи обходы", "покажи запрет"
        ]
        for zmp in zapret_menu_triggers:
            if zmp in text_low:
                return "start_zapret"

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

        spotify_case_triggers = [
            "спотифай", "спотифая", "спотифаю", "спотифаем", "спотифае",
            "спотик", "спотика", "спотику", "спотиком", "спотике",
            "споти", "spotify"
        ]
        if any(trig in text_low for trig in spotify_case_triggers):
            if any(verb in text_low for verb in
                   ["включ", "постав", "сыграй", "вруби", "запуст", "проиграй", "найди", "открой", "слуша"]):
                return "play_music"

        if len(words) > 7:
            strict_command_roots = [
                "включ", "постав", "сыграй", "вруби", "запуст",
                "выключ", "перезагруз", "погод", "градус", "громкост",
                "потише", "погромче", "скрин", "залочь", "заблокируй",
                "спотик", "спотиф", "яндекс", "музык", "трек", "песн", "запрет", "обход", "работ", "отдых"
            ]
            if not any(
                    root in text_low for root in strict_command_roots) and not has_generic_vpn and parsed_vpn == "none":
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
            "давай другой", "давай еще анекдот", "давай ещё анекдот", "как настроение",
            "твое настроение", "как твое здоровье", "здоровье", "настроение"
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

    def process_command(self, text, audio_data=None, is_voice=False, attached_file=None):
        if not text and not attached_file:
            return ""

        text_low = text.lower().strip() if text else ""

        emotion, emo_conf = self.emotion_classifier.predict(audio_data)
        self.last_emotion = emotion
        emo_desc = EMOTION_TRANSLATION.get(emotion, "нейтральный")

        if attached_file:
            file_text = self.doc_parser.parse_file(attached_file)

            if len(file_text) > 15000:
                file_text = file_text[:15000] + "\n\n... [Текст обрезан из-за лимита токенов]"

            if file_text.strip():
                prompt = text if text else "Изучи этот документ и расскажи кратко, о чем он."
                ans = self.llm.ask_with_context(prompt, file_text)
                return {"chat": ans, "voice": ans, "emotion": emotion}
            else:
                msg = "Не удалось распознать текст в этом файле."
                return {"chat": msg, "voice": msg, "emotion": emotion}

        if self.waiting_for_tg_msg:
            if any(w in text_low for w in ["отмена", "забудь", "не надо", "хватит", "стоп"]):
                self.waiting_for_tg_msg = False
                self.tg_recipient = None
                return {
                    "chat": "Отправка сообщения отменена.",
                    "voice": "Отменила отправку.",
                    "emotion": emotion
                }

            msg_to_send = text
            target = self.tg_recipient
            self.waiting_for_tg_msg = False
            self.tg_recipient = None

            success, info = self.tg_user_mgr.send_message_sync(target, msg_to_send)
            if success:
                return {
                    "chat": f"Сообщение для {target.title()} отправлено: «{msg_to_send}»",
                    "voice": "Отправила!",
                    "emotion": emotion
                }
            else:
                return {
                    "chat": f"Не удалось отправить: {info}",
                    "voice": "Не смогла отправить сообщение.",
                    "emotion": emotion
                }

        tg_match = re.search(
            r'\b(?:отправь сообщение|напиши сообщение|напиши|отправь)\s+(?:контакту\s+)?([а-яa-z0-9_@]+)', text_low)
        if tg_match and not any(w in text_low for w in ["музык", "трек", "видео", "обход", "запрет", "пк", "комп"]):
            target_name = tg_match.group(1).strip()
            self.waiting_for_tg_msg = True
            self.tg_recipient = target_name
            return {
                "chat": f"Кому: {target_name.title()}. Что отправить?",
                "voice": "Что отправить?",
                "emotion": emotion
            }

        if self.waiting_for_zapret:
            num = self._extract_zapret_number(text_low)
            if num is not None:
                self.waiting_for_zapret = False
                res_text = zapret_manager.start_strategy_by_index(num)
                return {
                    "chat": res_text,
                    "voice": res_text,
                    "emotion": emotion
                }
            if any(w in text_low for w in ["отмена", "забудь", "не надо", "назад", "хватит", "стоп"]):
                self.waiting_for_zapret = False
                return {
                    "chat": "Выбор варианта обхода отменён.",
                    "voice": "Отменила выбор обхода.",
                    "emotion": emotion
                }
            return {
                "chat": "Пожалуйста, назови или введи номер от 1 до 20 (или напиши 'отмена').",
                "voice": "Скажи или введи число от одного до двадцати.",
                "emotion": emotion
            }

        if self.waiting_for_vpn:
            if any(w in text_low for w in ["отмена", "забудь", "не надо", "назад", "хватит", "стоп"]):
                self.waiting_for_vpn = False
                return {
                    "chat": "" if is_voice else "Выбор впн отменён.",
                    "voice": "Отменила выбор впн.",
                    "emotion": emotion
                }
            vpn_key = vpn_manager.parse_vpn_name(text_low)
            if vpn_key != "none":
                self.waiting_for_vpn = False
                vpn_manager.set_configured_vpn(vpn_key)
                res_text = vpn_manager.connect(vpn_key)
                return {
                    "chat": "" if is_voice else f"Запомнила {vpn_key.title()}! {res_text}",
                    "voice": f"Запомнила! {res_text}",
                    "emotion": emotion
                }
            return {
                "chat": "Не распознала клиент. Назови или напиши: Сота, Хапп, Витурей или Ваергард (или 'отмена').",
                "voice": "Назови приложение: Сота, Хапп, Витурей или Ваергард.",
                "emotion": emotion
            }

        num_direct = self._extract_zapret_number(text_low)
        if num_direct is not None and any(w in text_low for w in ["обход", "стратеги", "вариант", "запрет"]):
            res_text = zapret_manager.start_strategy_by_index(num_direct)
            return {
                "chat": res_text,
                "voice": res_text,
                "emotion": emotion
            }

        rule_intent = self._check_rules(text)

        if rule_intent == "start_zapret":
            self.waiting_for_zapret = True
            res = SystemActions.start_zapret(text)
            if isinstance(res, dict):
                res["emotion"] = emotion
                return res
            return {"chat": str(res), "voice": str(res), "emotion": emotion}

        if rule_intent == "stop_zapret":
            self.waiting_for_zapret = False
            res = SystemActions.stop_zapret(text)
            return {"chat": str(res), "voice": str(res), "emotion": emotion}

        if rule_intent == "start_vpn":
            explicit_vpn = vpn_manager.parse_vpn_name(text_low)
            if explicit_vpn != "none":
                res = vpn_manager.connect(explicit_vpn)
                return {"chat": "" if is_voice else res, "voice": res, "emotion": emotion}

            configured = vpn_manager.get_configured_vpn()
            if configured == "none":
                self.waiting_for_vpn = True
                return {
                    "chat": "Какое приложение для ВПН ты используешь? (Сота, Хапп, Витурей или Ваергард)",
                    "voice": "Какое приложение для ВПН ты используешь?",
                    "emotion": emotion
                }
            res = vpn_manager.connect(configured)
            return {"chat": "" if is_voice else res, "voice": res, "emotion": emotion}

        if rule_intent == "stop_vpn":
            explicit_vpn = vpn_manager.parse_vpn_name(text_low)
            if explicit_vpn != "none":
                res = vpn_manager.disconnect(explicit_vpn)
                return {"chat": "" if is_voice else res, "voice": res, "emotion": emotion}

            configured = vpn_manager.get_configured_vpn()
            if configured == "none" and not vpn_manager.last_active_vpn:
                return {
                    "chat": "" if is_voice else "ВПН не выбран в настройках.",
                    "voice": "ВПН не выбран в настройках.",
                    "emotion": emotion
                }
            res = vpn_manager.disconnect()
            return {"chat": "" if is_voice else res, "voice": res, "emotion": emotion}

        if rule_intent == "chat":
            prompt_with_emotion = f"[{emo_desc}] {text}" if emotion in ["sad", "happy"] else text
            ans = self.llm.ask(prompt_with_emotion)
            return {"chat": ans, "voice": ans, "emotion": emotion}

        if not self.is_ready:
            self.loader_thread.join()

        intent = None
        slots = {}

        if rule_intent:
            intent = rule_intent
            if self.nlu:
                _, _, slots = self.nlu.predict(text)
        else:
            if self.nlu:
                intent, confidence, slots = self.nlu.predict(text)
                if confidence < self.threshold:
                    intent = None

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
                    res_str = str(res)
                    if emotion == "sad" and intent in ["play_music", "mode_rest"]:
                        res_str = f"{res_str}... Надеюсь, это поможет тебе почувствовать себя лучше 💛 Если захочешь выговориться — я рядом."
                    elif emotion == "happy" and intent in ["play_music", "mode_rest"]:
                        res_str = f"{res_str}! Рада твоему классному настроению ✨"

                    if intent in ["start_vpn", "stop_vpn"]:
                        return {"chat": "" if is_voice else res_str, "voice": res_str, "emotion": emotion}
                    return {"chat": res_str, "voice": res_str, "emotion": emotion}

        prompt_with_emotion = f"[Интонация пользователя: {emo_desc}] {text}" if emotion in ["sad", "happy"] else text
        ans = self.llm.ask(prompt_with_emotion)
        return {"chat": ans, "voice": ans, "emotion": emotion}