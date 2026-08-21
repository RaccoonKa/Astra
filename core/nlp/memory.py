import os
import json
import threading


class MemoryManager:
    def __init__(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(os.path.dirname(script_dir))
        self.memory_file = os.path.join(project_dir, "personal_data", "configs", "user_memory.json")
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
        if not client or len(user_text.strip()) < 5:
            return

        ignore_phrases = [
            "включи", "выключи", "поставь", "пауза", "громкость",
            "погода", "запусти", "открой", "найди", "сколько время"
        ]
        low_text = user_text.lower()
        if any(low_text.startswith(p) for p in ignore_phrases) and "запомни" not in low_text:
            return

        extraction_prompt = (
            "Проанализируй диалог и выдели постоянные факты о пользователе (его имя, увлечения, проекты, предпочтения, привычки, важные детали жизни), если они явно прозвучали.\n"
            "Если новой постоянной информации нет, ответь строго: НЕТ\n"
            "Если есть факт, сформулируй его кратко в одно предложение от третьего лица (например: 'Пользователь пишет проект на Python', 'Любит слушать рок'). "
            "Не придумывай ничего лишнего.\n\n"
            f"Сообщение пользователя: {user_text}\n"
            f"Ответ ассистента: {assistant_reply}\n\n"
            "Факт:"
        )

        try:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": extraction_prompt}]
            }
            response = client.chat(payload)
            result = response.choices[0].message.content.strip()

            if result and "НЕТ" not in result.upper() and len(result) < 150:
                clean_fact = result.replace("Факт:", "").strip()
                if clean_fact:
                    self.add_fact(clean_fact)
        except Exception:
            pass