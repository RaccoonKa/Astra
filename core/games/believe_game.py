import os
import json
import random
from core.utils.config import get_resource_path, load_config

NUMS_NOM = {
    0: "ноль", 1: "один", 2: "два", 3: "три", 4: "четыре", 5: "пять",
    6: "шесть", 7: "семь", 8: "восемь", 9: "девять", 10: "десять",
    11: "одиннадцать", 12: "двенадцать", 13: "тринадцать", 14: "четырнадцать",
    15: "пятнадцать", 16: "шестнадцать", 17: "семнадцать", 18: "восемнадцать",
    19: "девятнадцать", 20: "двадцать", 30: "тридцать", 40: "сорок",
    50: "пятьдесят", 60: "шестьдесят", 70: "семьдесят", 80: "восемьдесят",
    90: "девяносто", 100: "сто"
}

NUMS_GEN = {
    0: "нуля", 1: "одного", 2: "двух", 3: "трёх", 4: "четырёх", 5: "пяти",
    6: "шести", 7: "семи", 8: "восьми", 9: "девяти", 10: "десяти",
    11: "одиннадцати", 12: "двенадцати", 13: "тринадцати", 14: "четырнадцати",
    15: "пятнадцати", 16: "шестнадцати", 17: "семнадцати", 18: "восемнадцати",
    19: "девятнадцати", 20: "двадцати", 30: "тридцати", 40: "сорока",
    50: "пятидесяти", 60: "шестидесяти", 70: "семидесяти", 80: "восьмидесяти",
    90: "девяноста", 100: "ста"
}


class BelieveGame:
    def __init__(self):
        self.is_active = False
        self.facts = []
        self.unused_indices = []
        self.current_fact = None
        self.score = 0
        self.total_rounds = 0
        self._load_facts()

    def _load_facts(self):
        path = get_resource_path("assets", "games", "believe_facts.json")
        if not os.path.exists(path):
            path = get_resource_path("personal_data", "games", "believe_facts.json")

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.facts = json.load(f)
            except Exception as e:
                print(f"[BelieveGame Load Error]: {e}", flush=True)

    @staticmethod
    def _num_to_nom(n: int) -> str:
        if n in NUMS_NOM:
            return NUMS_NOM[n]
        tens = (n // 10) * 10
        units = n % 10
        if tens in NUMS_NOM and units in NUMS_NOM:
            return f"{NUMS_NOM[tens]} {NUMS_NOM[units]}"
        return str(n)

    @staticmethod
    def _num_to_gen(n: int) -> str:
        if n in NUMS_GEN:
            return NUMS_GEN[n]
        tens = (n // 10) * 10
        units = n % 10
        if tens in NUMS_GEN and units in NUMS_GEN:
            return f"{NUMS_GEN[tens]} {NUMS_GEN[units]}"
        return str(n)

    def _get_miss_phrase(self) -> str:
        cfg = load_config()
        gender = cfg.get("user_gender", "male").lower()
        if gender == "female":
            return "А вот и не угадала!"
        return "А вот и не угадал!"

    def start_game(self) -> dict:
        if not self.facts:
            return {
                "chat": "У меня пока нет списка фактов для этой игры.",
                "voice": "У меня пока нет списка фактов для этой игры.",
                "emotion": "neutral",
                "followup": False
            }

        self.is_active = True
        self.score = 0
        self.total_rounds = 0
        self.unused_indices = list(range(len(self.facts)))
        random.shuffle(self.unused_indices)

        idx = self.unused_indices.pop()
        self.current_fact = self.facts[idx]

        ans = (
            f"Отлично, играем в «Верю — не верю»! Я говорю факт, а ты отвечаешь «Верю» или «Не верю». "
            f"Первый факт: {self.current_fact['fact']} Веришь?"
        )
        return {
            "chat": ans,
            "voice": ans,
            "emotion": "happy",
            "followup": True
        }

    def stop_game(self) -> dict:
        self.is_active = False
        self.current_fact = None

        if self.total_rounds > 0:
            nom_score = self._num_to_nom(self.score)
            gen_total = self._num_to_gen(self.total_rounds)
            chat_ans = f"Игра окончена! Твой счёт: {self.score} из {self.total_rounds}. Отличная разминка для ума ✨"
            voice_ans = f"Игра окончена! Твой счёт: {nom_score} из {gen_total}. Отличная разминка для ума."
        else:
            chat_ans = voice_ans = "Закончили игру! Возвращаюсь к делам."

        return {
            "chat": chat_ans,
            "voice": voice_ans,
            "emotion": "happy" if self.score > 0 else "neutral",
            "followup": False
        }

    def handle_turn(self, text: str) -> dict:
        text_clean = text.lower().strip()

        stop_words = ["стоп", "хватит", "закончим", "не хочу", "надоело", "отмена", "выход", "сдаюсь"]
        if any(w in text_clean for w in stop_words):
            return self.stop_game()

        yes_words = ["верю", "правда", "да", "верно", "точно", "ага", "правдиво", "верю верю", "бывает"]
        no_words = ["не верю", "ложь", "нет", "неверно", "неправда", "неа", "вранье", "враньё", "чушь"]

        user_answer = None
        if any(w in text_clean for w in no_words):
            user_answer = False
        elif any(w in text_clean for w in yes_words):
            user_answer = True

        if user_answer is None:
            ans = "Не поняла твой ответ. Скажи просто: «Верю» или «Не верю»!"
            return {
                "chat": ans,
                "voice": ans,
                "emotion": "surprise",
                "followup": True
            }

        self.total_rounds += 1
        correct_answer = self.current_fact.get("answer", True)
        explanation = self.current_fact.get("explanation", "")

        if user_answer == correct_answer:
            self.score += 1
            verdict = "В точку! 👍"
            emo = "happy"
        else:
            verdict = f"{self._get_miss_phrase()} 🙃"
            emo = "surprise"

        exp_part = f" {explanation}" if explanation else ""

        if not self.unused_indices:
            self.is_active = False
            nom_score = self._num_to_nom(self.score)
            gen_total = self._num_to_gen(self.total_rounds)
            chat_ans = f"{verdict}{exp_part} У меня закончились факты! Твой итоговый счёт: {self.score} из {self.total_rounds}! 🎉"
            voice_ans = f"{verdict}{exp_part} У меня закончились факты! Твой итоговый счёт: {nom_score} из {gen_total}."
            return {
                "chat": chat_ans,
                "voice": voice_ans,
                "emotion": "happy",
                "followup": False
            }

        next_idx = self.unused_indices.pop()
        self.current_fact = self.facts[next_idx]

        ans = f"{verdict}{exp_part} Следующий факт: {self.current_fact['fact']} Веришь?"
        return {
            "chat": ans,
            "voice": ans,
            "emotion": emo,
            "followup": True
        }