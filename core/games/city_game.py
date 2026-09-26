import os
import re
import json
import random
from core.utils.config import get_resource_path, load_config

BAD_ENDINGS = {'ь', 'ъ', 'ы'}


class CityGame:
    def __init__(self, llm_provider=None):
        self.llm = llm_provider
        self.is_active = False
        self.cities = set()
        self.original_names = {}
        self.used_cities = set()
        self.current_letter = None
        self.last_astra_city = None
        self._load_cities()

    def _load_cities(self):
        path = get_resource_path("assets", "games", "cities.json")
        if not os.path.exists(path):
            path = get_resource_path("personal_data", "games", "cities.json")

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                    for item in raw_list:
                        name = item.strip()
                        if name:
                            low = name.lower()
                            self.cities.add(low)
                            self.original_names[low] = name
            except Exception as e:
                print(f"[CityGame Load Error]: {e}", flush=True)

    def _get_target_letter(self, city_name: str) -> str:
        for char in reversed(city_name.lower()):
            if char not in BAD_ENDINGS:
                return char
        return city_name[-1].lower()

    def _get_gender_trick_phrase(self) -> str:
        cfg = load_config()
        gender = cfg.get("user_gender", "male").lower()
        if gender == "female":
            return "Хитрая какая! Нет такого города на карте мира, давай нормальный!"
        return "Хитрый какой! Нет такого города на карте мира, давай нормальный!"

    def _has_gigachat(self) -> bool:
        cfg = load_config()
        key = cfg.get("api_keys", {}).get("gigachat", "").strip()
        return bool(key and self.llm)

    def _verify_with_gigachat(self, city_name: str) -> bool:
        prompt = (
            f"Ответь строго одним словом: ДА или НЕТ.\n"
            f"Существует ли в реальном мире город или населённый пункт с названием \"{city_name}\"?"
        )
        try:
            res = self.llm.ask(prompt, raw_user_text=city_name).strip().upper()
            return "ДА" in res
        except Exception:
            return False

    def _explain_city(self, city_name: str) -> str:
        prompt = (
            f"Кратко в одном или двух простых предложениях расскажи, "
            f"где находится город {city_name} и чем он примечателен."
        )
        try:
            return self.llm.ask(prompt, raw_user_text=city_name).strip()
        except Exception:
            return f"{city_name} — это существующий город, поверь мне на слово!"

    def start_game(self) -> dict:
        self.is_active = True
        self.used_cities.clear()

        start_city_low = random.choice(list(self.cities)) if self.cities else "москва"
        display_name = self.original_names.get(start_city_low, start_city_low.title())

        self.used_cities.add(start_city_low)
        self.last_astra_city = display_name
        self.current_letter = self._get_target_letter(start_city_low)

        ans = (
            f"Отлично, играем в города! Чур я начинаю: {display_name}! "
            f"Тебе на букву {self.current_letter.upper()}."
        )
        return {
            "chat": ans,
            "voice": ans,
            "emotion": "happy",
            "followup": True
        }

    def stop_game(self, surrender=False) -> dict:
        self.is_active = False
        self.used_cities.clear()
        self.current_letter = None
        self.last_astra_city = None

        if surrender:
            ans = "Ура, победа за мной! Отличная партия получилась ✨"
            emo = "happy"
        else:
            ans = "Закончили игру в города! Возвращаюсь к обычным делам."
            emo = "neutral"

        return {
            "chat": ans,
            "voice": ans,
            "emotion": emo,
            "followup": False
        }

    def handle_turn(self, text: str) -> dict:
        text_clean = text.lower().strip()

        surrender_words = ["сдаюсь", "я сдаюсь", "ты победила", "ты выиграла", "не знаю", "не помню"]
        if any(w in text_clean for w in surrender_words):
            return self.stop_game(surrender=True)

        stop_words = ["стоп", "хватит", "закончим", "не хочу", "надоело", "отмена", "выход"]
        if any(w in text_clean for w in stop_words):
            return self.stop_game(surrender=False)

        inquiry_words = ["что за город", "что это за город", "где это", "где он находится", "где находится", "не знаю такой"]
        if any(w in text_clean for w in inquiry_words) and self.last_astra_city:
            if self._has_gigachat():
                desc = self._explain_city(self.last_astra_city)
                ans = f"{desc} Жду твой ход на букву {self.current_letter.upper()}!"
            else:
                ans = f"{self.last_astra_city} — абсолютно реальный город! Называй свой на букву {self.current_letter.upper()}."
            return {
                "chat": ans,
                "voice": ans,
                "emotion": "neutral",
                "followup": True
            }

        city_candidate = re.sub(r'^(?:город|это|мой город|называю)\s+', '', text_clean).strip()
        city_candidate = re.sub(r'[^\w\s\-]', '', city_candidate).strip()

        if not city_candidate:
            ans = f"Назови город на букву {self.current_letter.upper()}."
            return {"chat": ans, "voice": ans, "emotion": "neutral", "followup": True}

        first_char = city_candidate[0]
        if first_char != self.current_letter:
            ans = f"Нужен город на букву {self.current_letter.upper()}, а ты назвал на {first_char.upper()}! Попробуй ещё раз."
            return {"chat": ans, "voice": ans, "emotion": "surprise", "followup": True}

        if city_candidate in self.used_cities:
            ans = f"Город {city_candidate.title()} уже был! Вспоминай другой на букву {self.current_letter.upper()}."
            return {"chat": ans, "voice": ans, "emotion": "surprise", "followup": True}

        if city_candidate not in self.cities:
            if not self._has_gigachat():
                ans = f"В моём атласе такого города нет! Назови другой на букву {self.current_letter.upper()}."
                return {"chat": ans, "voice": ans, "emotion": "surprise", "followup": True}

            is_real = self._verify_with_gigachat(city_candidate)
            if not is_real:
                ans = f"{self._get_gender_trick_phrase()} Жду город на букву {self.current_letter.upper()}."
                return {"chat": ans, "voice": ans, "emotion": "angry", "followup": True}

            self.cities.add(city_candidate)
            self.original_names[city_candidate] = city_candidate.title()

        self.used_cities.add(city_candidate)
        next_letter_for_astra = self._get_target_letter(city_candidate)

        available_cities = [
            c for c in self.cities
            if c.startswith(next_letter_for_astra) and c not in self.used_cities
        ]

        if not available_cities:
            self.is_active = False
            ans = f"Ого! Я не знаю больше городов на букву {next_letter_for_astra.upper()}. Ты победил! 🎉"
            return {"chat": ans, "voice": ans, "emotion": "surprise", "followup": False}

        astra_chosen = random.choice(available_cities)
        self.used_cities.add(astra_chosen)
        self.last_astra_city = self.original_names.get(astra_chosen, astra_chosen.title())
        self.current_letter = self._get_target_letter(astra_chosen)

        ans = f"{self.last_astra_city}! Тебе на букву {self.current_letter.upper()}."
        return {
            "chat": ans,
            "voice": ans,
            "emotion": "happy",
            "followup": True
        }