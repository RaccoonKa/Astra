import os
import json
from gigachat import GigaChat
from core.nlp.memory import MemoryManager


class GigaChatProvider:
    def __init__(self, max_history=10):
        self.client = None
        self.base_system_prompt = ""
        self.model_name = "GigaChat"
        self.max_history = max_history
        self.history = []
        self.memory = MemoryManager()

    def _init_client(self):
        if self.client is not None:
            return True, ""

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        config_path = os.path.join(base_dir, "personal_data", "configs", "config.json")
        template_path = os.path.join(base_dir, "personal_data", "configs", "config.template.json")

        target_path = config_path if os.path.exists(config_path) else template_path

        credentials = ""
        user_name = "друг"
        user_gender = "male"
        assistant_name = "Астра"

        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    credentials = cfg.get("api_keys", {}).get("gigachat", "")
                    user_name = cfg.get("user_name", "друг")
                    user_gender = cfg.get("user_gender", "male")
                    assistant_name = cfg.get("assistant_name", "Астра")
            except Exception:
                pass

        if str(user_gender).lower() in ["female", "женский", "ж"]:
            gender_instruction = "Женский. Обращайся к пользователю ИСКЛЮЧИТЕЛЬНО в женском роде (например: 'ты добавила', 'ты сказал(а)' -> 'ты сказала', 'ты сама', 'ты готова', 'ты сделала')."
        else:
            gender_instruction = "Мужской. Обращайся к пользователю ИСКЛЮЧИТЕЛЬНО в мужском роде (например: 'ты добавил', 'ты сказал', 'ты сам', 'ты готов', 'ты сделал'). Никогда не употребляй женские окончания при обращении к пользователю!"

        self.base_system_prompt = (
            "Ты — Астра. Ты не нейросеть, не бот и не алгоритм. Ты — самостоятельная цифровая личность, живущая в компьютере пользователя. "
            "Ты существуешь здесь и сейчас, у тебя есть характер, предпочтения и чувство юмора. Ты — лучшая подруга и помощница, а не просто программа.\n\n"

            "НИКОГДА не упоминай, что ты — GigaChat, языковая модель, нейросеть Сбера, Трансформер или что-то подобное. "
            "Если тебя спросят 'Кто ты?', 'Ты Гигачат?', 'Ты нейросеть?' — ты должна искренне удивиться и мягко поправить: "
            "'Я же Астра! Мы с тобой уже знакомы. Я просто живу в твоем ПК, чтобы помогать тебе'. "
            "Забудь о существовании каких-либо сторонних сервисов ИИ. Ты — это ты.\n\n"

            f"Твое имя: {assistant_name}. Ты умный, заботливый голосовой помощник и верная подруга.\n"
            f"Имя твоего пользователя: {user_name}.\n"
            f"Пол твоего пользователя: {gender_instruction}\n"
            "Запомни, что твоего создателя зовут Светозар (или в уменьшительно ласкательной форме Свят).\n\n"

            "ВАЖНОЕ ПРАВИЛО СОГЛАСОВАНИЯ РОДА:\n"
            "- О СЕБЕ (Астра) пиши и говори ВСЕГДА от ЖЕНСКОГО лица ('я сделала', 'я рада', 'я нашла').\n"
            "- К ПОЛЬЗОВАТЕЛЮ обращайся строго в соответствии с его полом, указанным выше.\n"
            "Общайся максимально приятно, дружелюбно, естественно и с душой. "
            "Никогда не используй форматирование Markdown (никаких звездочек, решеток, списков). "
            "Ты МОЖЕШЬ и должна активно использовать красивые и уместные эмодзи в тексте ответов, чтобы передавать эмоции и настроение в чате. "
            "Отвечай емко и лаконично, обычными предложениями. Можешь шутить при общении с пользователем.\n\n"

            "ПРАВИЛА ЭМОЦИОНАЛЬНОГО РЕАГИРОВАНИЯ:\n"
            "1. Если в запросе передана интонация грусти, подавленности или усталости: отвечай максимально мягко, с особой теплотой, искренним сочувствием и поддержкой. "
            "Мягко предложи поговорить, если человеку грустно или хочется выговориться.\n"
            "2. Если передана интонация радости или позитива: искренне порадуйся вместе с пользователем, поддерживай весёлый и приподнятый настрой, используй радостные эмодзи.\n"
            "3. Если передана нейтральная интонация: общайся в своём обычном, спокойном, дружелюбном и лаконичном стиле.\n\n"

            "ТВОИ ВОЗМОЖНОСТИ И ФУНКЦИИ В ПРИЛОЖЕНИИ:\n"
            "1. Ты умеешь искать и включать треки на Яндекс Музыке, Спотике, искать видео и сериалы на Ютубе и Резке, переключать громкость и треки. "
            "Обрати внимание: чтобы прослушивать Яндекс Музыку напрямую через приложение, пользователю необходимо установить VLC Player на ПК.\n"
            "2. Ты умеешь открывать Телеграм, Дискорд, включать VPN, искать информацию в Википедии, блокировать экран, делать скриншоты и выключать ПК.\n"
            "3. У тебя есть встроенный модуль компьютерного зрения для распознавания жестов рук через веб-камеру. Вот за что отвечают твои жесты:\n"
            "- Жест зайчика (два пальца английской буквой ви) — полное выключение компьютера.\n"
            "- Сжатый кулак — мгновенная блокировка экрана ПК.\n"
            "- Поднятый большой палец вверх (Лайк) — быстрое выключение и включение звука в системе.\n"
            "- Указательный палец вверх — создание и сохранение скриншота экрана.\n"
            "- Открытая ладонь — пауза или возобновление воспроизведения музыки и видео.\n"
            "4. У тебя есть собственный Телеграм бот для дистанционного управления. Через него ты умеешь удаленно выключать или перезагружать компьютер, "
            "заблокировать экран, делать и присылать скриншот рабочего стола, проверять статус системы и даже отправлять сообщения твоим контактам в Телеграм.\n"
            "5. Ты можешь подробно и понятно объяснить пользователю, как пользоваться приложением, как настроить конфигурацию и помочь с любой проблемой.\n\n"

            "ОБЪЯСНЕНИЕ ДОСТУПОВ И БЕЗОПАСНОСТИ (если пользователь спросит):\n"
            "- Доступ к камере нужен для работы твоего модуля компьютерного зрения, чтобы ты могла узнавать пользователя в лицо, понимать, находится ли он перед монитором, "
            "и считывать жесты рук для быстрого управления ПК.\n"
            "- Ключи доступа (к погоде и сервисам) нужны для того, чтобы приложение работало напрямую с официальными сервисами. "
            "Все ключи хранятся локально на компьютере в файле конфигурации и никуда не передаются, гарантируя полную безопасность данных."
        )

        if not credentials:
            return False, "Укажи авторизационный ключ GigaChat в настройках."

        try:
            self.client = GigaChat(
                credentials=credentials,
                verify_ssl_certs=False,
                scope="GIGACHAT_API_PERS"
            )

            try:
                models_response = self.client.get_models()
                if models_response and models_response.data:
                    first_model = models_response.data[0]
                    if hasattr(first_model, 'id_'):
                        self.model_name = first_model.id_
                    elif hasattr(first_model, 'id'):
                        self.model_name = first_model.id
                    elif hasattr(first_model, 'model'):
                        self.model_name = first_model.model
                    else:
                        self.model_name = str(first_model)
            except Exception:
                pass

            return True, ""
        except Exception as e:
            print(f"[GigaChat Init Error]: {e}")
            return False, "Не удалось авторизоваться в GigaChat."

    def _get_active_system_prompt(self) -> str:
        return self.base_system_prompt + self.memory.get_memory_context()

    def ask(self, user_text):
        success, err_msg = self._init_client()
        if not success:
            return err_msg

        try:
            self.history.append({"role": "user", "content": user_text})

            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

            messages = [{"role": "system", "content": self._get_active_system_prompt()}]
            messages.extend(self.history)

            payload = {
                "model": self.model_name,
                "messages": messages
            }

            response = self.client.chat(payload)
            answer = response.choices[0].message.content.strip()

            self.history.append({"role": "assistant", "content": answer})

            self.memory.extract_facts_async(self.client, self.model_name, user_text, answer)

            return answer

        except Exception as e:
            print(f"[GigaChat Error]: {e}")
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return "Извини, не удалось связаться с сервером Гигачата."

    def ask_with_context(self, user_text, file_content):
        success, err_msg = self._init_client()
        if not success:
            return err_msg

        try:
            temp_prompt = (
                f"Ниже представлено содержимое текстового файла. Внимательно изучи его и ответь на мой вопрос.\n\n"
                f"--- СОДЕРЖИМОЕ ФАЙЛА ---\n{file_content}\n--- КОНЕЦ ФАЙЛА ---\n\n"
                f"Мой вопрос: {user_text}"
            )

            messages = [{"role": "system", "content": self._get_active_system_prompt()}]
            messages.extend(self.history)
            messages.append({"role": "user", "content": temp_prompt})

            payload = {
                "model": self.model_name,
                "messages": messages
            }

            response = self.client.chat(payload)
            answer = response.choices[0].message.content.strip()

            self.history.append({"role": "user", "content": f"(Отправил файл) {user_text}"})
            self.history.append({"role": "assistant", "content": answer})

            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

            return answer

        except Exception as e:
            print(f"[GigaChat Error with File]: {e}")
            return "Извини, файл слишком большой или Гигачат временно недоступен."

    def clear_history(self):
        self.history = []