import sys
import json
import asyncio
from pathlib import Path
from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT_DIR / "personal_data" / "configs" / "config.json"
SESSION_PATH = str(ROOT_DIR / "personal_data" / "configs" / "user_session")

async def main():
    if not CONFIG_PATH.exists():
        print("Файл config.json не найден!")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    api_id = cfg.get("api_keys", {}).get("telegram_api_id")
    api_hash = cfg.get("api_keys", {}).get("telegram_api_hash")

    if not api_id or not api_hash:
        print("Заполни telegram_api_id и telegram_api_hash в config.json!")
        return

    client = TelegramClient(SESSION_PATH, int(api_id), api_hash)
    await client.start()
    print("\nАвторизация успешна! Файл сессии создан. Теперь Астра может отправлять сообщения.")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())