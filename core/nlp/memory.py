import os
import json
import threading
from core.utils.config import get_user_data_path


class MemoryManager:
    def __init__(self):
        self.memory_file = get_user_data_path("user_memory.json")
        self.lock = threading.Lock()
        self.facts = self._load_facts()

    def _load_facts(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get("facts", [])
            except Exception:
                pass
        return []

    def _save_facts(self):
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump({"facts": self.facts}, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def add_fact(self, fact: str):
        fact = fact.strip()
        if not fact:
            return

        with self.lock:
            if fact not in self.facts:
                self.facts.append(fact)
                if len(self.facts) > 40:
                    self.facts = self.facts[-40:]
                self._save_facts()

    def clear_memory(self):
        with self.lock:
            self.facts = []
            self._save_facts()

    def get_memory_context(self) -> str:
        with self.lock:
            if not self.facts:
                return ""
            formatted_facts = "\n".join([f"- {fact}" for fact in self.facts])
            return f"\n\nФАКТЫ И ВОСПОМИНАНИЯ О ПОЛЬЗОВАТЕЛЕ (ДОЛГОВРЕМЕННАЯ ПАМЯТЬ):\n{formatted_facts}\nИспользуй эти факты естественным образом в общении, если это уместно."

    def extract_facts_async(self, client, model_name: str, user_text: str, assistant_reply: str):
        threading.Thread(
            target=self._extract_worker,
            args=(client, model_name, user_text, assistant_reply),
            daemon=True
        ).start()

    def _extract_worker(self, client, model_name: str, user_text: str, assistant_reply: str):
        if not client or len(user_text.strip()) < 6:
            return

        ignore_prefixes = (
            "включи", "выключи", "поставь", "пауза", "громкость",
            "погода", "запусти", "открой", "найди", "сколько время", "покажи"
        )
        low_text = user_text.lower().strip()
        if low_text.startswith(ignore_prefixes) and "запомни" not in low_text:
            return

        extraction_prompt = (
            "Ты — аналитик диалога. Определи, сообщил ли пользователь в своей реплике какую-либо личную информацию о себе: "
            "своё имя, профессию, стек технологий, увлечения, любимые вещи, привычки или факты о своей жизни.\n\n"
            "ПРАВИЛА:\n"
            "1. Если пользователь просто задал вопрос, пошутил или поддержал разговор ни о чём — напиши ровно одно слово: НИЧЕГО\n"
            "2. Если есть реальный факт о пользователе — сформулируй его кратко от 3-го лица в одно предложение (например: 'Пользователь пишет код на Python', 'Любит чай без сахара').\n"
            "3. Не пиши вступительных слов, только сам факт или НИЧЕГО.\n\n"
            f"Реплика пользователя: {user_text}\n"
            f"Ответ ассистента: {assistant_reply}\n\n"
            "Результат:"
        )

        try:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": extraction_prompt}]
            }
            response = client.chat(payload)
            result = response.choices[0].message.content.strip()

            negative_markers = ["НИЧЕГО", "НЕТ", "ФАКТОВ НЕТ", "НЕТ НОВОЙ", "НЕТ ФАКТОВ"]
            clean_res = result.replace("Результат:", "").replace("Факт:", "").strip()

            if clean_res and clean_res.upper() not in negative_markers and not clean_res.upper().startswith("НЕТ"):
                if 5 <= len(clean_res) <= 140:
                    print(f"[Memory]: Новый факт в копилку -> '{clean_res}'", flush=True)
                    self.add_fact(clean_res)
        except Exception as e:
            print(f"[Memory Extract Error]: {e}", flush=True)