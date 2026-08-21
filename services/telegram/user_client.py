import os
import json
import asyncio
from pathlib import Path
from telethon import TelegramClient

class TelegramUserManager:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.config_path = self.base_dir / "personal_data" / "configs" / "config.json"
        self.session_path = str(self.base_dir / "personal_data" / "configs" / "user_session")

        self.api_id = None
        self.api_hash = None
        self._load_creds()

    def _load_creds(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    keys = cfg.get("api_keys", {})
                    raw_id = keys.get("telegram_api_id", "")
                    self.api_id = int(raw_id) if raw_id else None
                    self.api_hash = keys.get("telegram_api_hash", "")
            except Exception:
                pass

    def send_message_sync(self, recipient_query: str, message_text: str):
        return asyncio.run(self._send_message_async(recipient_query, message_text))

    async def _send_message_async(self, recipient_query: str, message_text: str):
        self._load_creds()
        if not self.api_id or not self.api_hash:
            return False, "Не указаны telegram_api_id или telegram_api_hash в настройках"

        client = TelegramClient(self.session_path, self.api_id, self.api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Сессия не авторизована. Требуется первичная авторизация"

        try:
            target_entity = None
            query_clean = recipient_query.lower().replace("@", "").strip()

            async for dialog in client.iter_dialogs():
                name = (dialog.name or "").lower()
                username = (getattr(dialog.entity, "username", "") or "").lower()

                if query_clean == username or query_clean in name or name in query_clean:
                    target_entity = dialog.entity
                    break

            if not target_entity:
                try:
                    target_entity = await client.get_entity(recipient_query)
                except Exception:
                    target_entity = None

            if not target_entity:
                await client.disconnect()
                return False, f"Диалог с '{recipient_query}' не найден"

            await client.send_message(target_entity, message_text)
            await client.disconnect()
            return True, "Отправила!"
        except Exception as e:
            await client.disconnect()
            return False, f"Ошибка: {e}"