import os
import json
import random
from core.utils.config import get_resource_path, load_config


class DanetkiGame:
    def __init__(self, llm_provider=None):
        self.llm = llm_provider
        self.is_active = False
        self.riddles = []
        self.unused_indices = []
        self.current_riddle = None
        self.history = []
        self._load_riddles()

    def _load_riddles(self):
        path = get_resource_path("assets", "games", "danetki.json")
        if not os.path.exists(path):
            path = get_resource_path("personal_data", "games", "danetki.json")

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.riddles = json.load(f)
            except Exception as e:
                print(f"[Danetki Load Error]: {e}", flush=True)

    def _has_gigachat(self) -> bool:
        cfg = load_config()
        key = cfg.get("api_keys", {}).get("gigachat", "").strip()
        return bool(key and self.llm)

    def start_game(self) -> dict:
        if not self._has_gigachat():
            ans = "Для игры в Данетки мне нужен доступ к Гигачату. Добавь API-ключ в настройках!"
            return {"chat": ans, "voice": ans, "emotion": "sad", "followup": False}

        if not self.riddles:
            ans = "У меня пока нет списка данеток в файлах."
            return {"chat": ans, "voice": ans, "emotion": "neutral", "followup": False}

        self.is_active = True
        self.history.clear()
        if not self.unused_indices:
            self.unused_indices = list(range(len(self.riddles)))
            random.shuffle(self.unused_indices)

        idx = self.unused_indices.pop()
        self.current_riddle = self.riddles[idx]

        ans = (
            f"Отлично, играем в Данетки! 🕵️‍♀️ Задавай любые вопросы, на которые я смогу ответить "
            f"только «Да», «Нет» или «Не имеет значения». А вот и загадка: "
            f"{self.current_riddle['riddle']}"
        )
        return {
            "chat": ans,
            "voice": ans,
            "emotion": "happy",
            "followup": True
        }

    def stop_game(self, reveal=False) -> dict:
        self.is_active = False
        solution = self.current_riddle.get("solution", "") if self.current_riddle else ""
        self.current_riddle = None
        self.history.clear()

        if reveal and solution:
            ans = f"Эх, сдаёшься? Вот как всё было на самом деле: {solution} 💡"
            emo = "surprise"
        else:
            ans = "Закончили расследование! Возвращаюсь к обычным делам."
            emo = "neutral"

        return {
            "chat": ans,
            "voice": ans,
            "emotion": emo,
            "followup": False
        }

    def handle_turn(self, text: str) -> dict:
        text_clean = text.lower().strip()

        surrender_words = ["сдаюсь", "я сдаюсь", "скажи ответ", "какой ответ", "не знаю", "в чём разгадка", "в чем разгадка"]
        if any(w in text_clean for w in surrender_words):
            return self.stop_game(reveal=True)

        stop_words = ["стоп", "хватит", "закончим", "не хочу", "надоело", "отмена", "выход"]
        if any(w in text_clean for w in stop_words):
            return self.stop_game(reveal=False)

        repeat_words = ["повтори", "напомни загадку", "в чём загадка", "в чем загадка", "какая загадка"]
        if any(w in text_clean for w in repeat_words) and self.current_riddle:
            ans = f"Напоминаю: {self.current_riddle['riddle']}"
            return {"chat": ans, "voice": ans, "emotion": "neutral", "followup": True}

        history_context = "\n".join(self.history[-6:]) if self.history else "Начало игры."
        prompt = (
            f"Ты беспристрастный ведущий детективной игры «Данетки».\n"
            f"Загадка: {self.current_riddle['riddle']}\n"
            f"Полная тайная разгадка: {self.current_riddle['solution']}\n\n"
            f"Предыдущий диалог:\n{history_context}\n\n"
            f"Вопрос или догадка игрока: \"{text}\"\n\n"
            f"Твоя задача — строго следовать правилам:\n"
            f"1. Если игрок разгадал суть истории или ключевую причину, начни ответ со слова 'РАЗГАДАНО!' и добавь пару тёплых предложений с подтверждением разгадки.\n"
            f"2. Если вопрос верный и соответствует разгадке — ответь 'Да.'\n"
            f"3. Если вопрос неверный — ответь 'Нет.'\n"
            f"4. Если факт не важен для разгадки истории — ответь 'Не имеет значения.'\n"
            f"5. Если игрок очень близко подобрался к ключевой детали — можешь сказать 'Да, ты очень близко к сути!'\n"
            f"6. Категорически запрещено спойлерить разгадку раньше времени или отвечать развёрнутыми фразами, если игрок ещё не разгадал тайну."
        )

        try:
            verdict = self.llm.ask(prompt, raw_user_text=text).strip()
        except Exception:
            verdict = "Не смогла обработать вопрос, попробуй сформулировать иначе."

        self.history.append(f"Игрок: {text}")
        self.history.append(f"Ведущий: {verdict}")

        if "РАЗГАДАНО!" in verdict:
            self.is_active = False
            self.current_riddle = None
            self.history.clear()
            clean_verdict = verdict.replace("РАЗГАДАНО!", "").strip()
            ans = f"Браво! Ты распутал это дело! 🎉 {clean_verdict}"
            return {
                "chat": ans,
                "voice": ans,
                "emotion": "happy",
                "followup": False
            }

        emo = "happy" if any(w in verdict.lower() for w in ["близко", "да"]) else "neutral"
        return {
            "chat": verdict,
            "voice": verdict,
            "emotion": emo,
            "followup": True
        }