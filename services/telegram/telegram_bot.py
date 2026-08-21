import asyncio
import os
import sys
import time
import json
import subprocess
from pathlib import Path
import cv2
import pyautogui
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from PyQt6.QtCore import QThread

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from personal_data.configs.config import load_config, save_config

CONFIG_PATH = ROOT_DIR / "personal_data" / "configs" / "config.json"
PAIRING_PATH = ROOT_DIR / "personal_data" / "configs" / "pairing_session.json"

dp = Dispatcher()
current_bot_instance = None

ERROR_UNREACHABLE_MSG = (
    "Я потеряла контакт с твоим ноутом 🥺\n"
    "Сигнал улетел в космос, попробуй чуть позже!"
)

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Скриншот"), KeyboardButton(text="Веб-камера")],
        [KeyboardButton(text="Заблокировать ПК"), KeyboardButton(text="Выключить ПК")]
    ],
    resize_keyboard=True
)

def get_admin_id() -> int:
    cfg = load_config()
    return int(cfg.get("api_keys", {}).get("telegram_admin_id", 0))

def check_and_pair_token(token_arg: str, user_id: int, user_name: str) -> bool:
    if not PAIRING_PATH.exists():
        return False

    try:
        with open(PAIRING_PATH, "r", encoding="utf-8") as f:
            session = json.load(f)

        valid_token = session.get("token")
        expires_at = session.get("expires_at", 0)

        if token_arg == valid_token and time.time() < expires_at:
            current_cfg = load_config()
            if "api_keys" not in current_cfg:
                current_cfg["api_keys"] = {}
            current_cfg["api_keys"]["telegram_admin_id"] = user_id
            current_cfg["user_name"] = user_name
            save_config(current_cfg)

            session["status"] = "paired"
            session["user_id"] = user_id
            session["user_name"] = user_name
            with open(PAIRING_PATH, "w", encoding="utf-8") as f:
                json.dump(session, f, ensure_ascii=False, indent=4)

            return True
    except Exception:
        pass
    return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    admin_id = get_admin_id()
    token_arg = command.args

    if token_arg:
        user_first_name = message.from_user.first_name or "друг"
        if check_and_pair_token(token_arg.strip(), message.from_user.id, user_first_name):
            await message.answer(
                f"Устройство успешно привязано к профилю {user_first_name}! Теперь я могу управлять твоим ПК.",
                reply_markup=main_keyboard
            )
            return
        else:
            await message.answer("Срок действия ссылки истек или код привязки недействителен.")
            return

    if admin_id != 0 and message.from_user.id == admin_id:
        await message.answer("Мой пульт дистанционного управления готов к работе!", reply_markup=main_keyboard)
        return

    await message.answer("Доступ запрещен. Открой мои настройки на компьютере и отсканируй QR-код для привязки.")

@dp.callback_query(F.data == "security_lock")
async def handle_security_lock(callback: types.CallbackQuery):
    if callback.from_user.id != get_admin_id():
        await callback.answer("Доступ запрещен!", show_alert=True)
        return
    try:
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        if callback.message:
            await callback.message.edit_caption(
                caption=f"{callback.message.caption or ''}\n\n🔒 Заблокировала твой ПК."
            )
        await callback.answer("ПК заблокирован!")
    except Exception:
        await callback.answer(ERROR_UNREACHABLE_MSG, show_alert=True)

@dp.callback_query(F.data == "security_ignore")
async def handle_security_ignore(callback: types.CallbackQuery):
    if callback.from_user.id != get_admin_id():
        await callback.answer("Доступ запрещен!", show_alert=True)
        return
    if callback.message:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption or ''}\n\n✅ Оставила доступ открытым!"
        )
    await callback.answer("Блокировка отменена.")

@dp.message(F.text == "Скриншот")
async def handle_screen(message: types.Message):
    if message.from_user.id != get_admin_id():
        return
    path = "temp_screen.png"
    try:
        pyautogui.screenshot(path)
        photo = FSInputFile(path)
        await message.answer_photo(photo, caption="Рабочий стол")
    except Exception:
        await message.answer(ERROR_UNREACHABLE_MSG)
    finally:
        if os.path.exists(path):
            os.remove(path)

@dp.message(F.text == "Веб-камера")
async def handle_cam(message: types.Message):
    if message.from_user.id != get_admin_id():
        return
    path = "temp_cam.png"
    try:
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()
        if ret:
            cv2.imwrite(path, frame)
            photo = FSInputFile(path)
            await message.answer_photo(photo, caption="Снимок с камеры")
        else:
            await message.answer("Ой, не могу включить камеру... Возможно, её уже заняло другое приложение 📷")
    except Exception:
        await message.answer(ERROR_UNREACHABLE_MSG)
    finally:
        if os.path.exists(path):
            os.remove(path)

@dp.message(F.text == "Заблокировать ПК")
async def handle_lock(message: types.Message):
    if message.from_user.id != get_admin_id():
        return
    try:
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        await message.answer("Заблокировала твой ПК.")
    except Exception:
        await message.answer(ERROR_UNREACHABLE_MSG)

@dp.message(F.text == "Выключить ПК")
async def handle_off(message: types.Message):
    if message.from_user.id != get_admin_id():
        return
    try:
        await message.answer("Выключаю ПК. До связи! 👋")
        subprocess.run("shutdown /s /t 5", shell=True)
    except Exception:
        await message.answer(ERROR_UNREACHABLE_MSG)

class TelegramBotThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = None
        self.bot = None

    def run(self):
        cfg = load_config()
        token = cfg.get("api_keys", {}).get("telegram_token", "")
        if not token:
            return

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.bot = Bot(token=token)
        global current_bot_instance
        current_bot_instance = self.bot

        try:
            self.loop.run_until_complete(dp.start_polling(self.bot))
        except Exception:
            pass
        finally:
            try:
                self.loop.run_until_complete(self.bot.session.close())
            except Exception:
                pass
            self.loop.close()

    def stop(self):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(dp.stop_polling(), self.loop)
        self.wait(1500)

async def main():
    cfg = load_config()
    token = cfg.get("api_keys", {}).get("telegram_token", "")
    if not token:
        print("[TELEGRAM BOT]: Токен бота не указан в config.json!")
        return
    bot = Bot(token=token)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())