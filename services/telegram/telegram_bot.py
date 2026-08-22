import asyncio
import os
import sys
import time
import json
import wave
import subprocess
from pathlib import Path
import psutil
import cv2
import pyautogui
import torch
import soundfile as sf
import sounddevice as sd
import numpy as np
import vosk
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from PyQt6.QtCore import QThread

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = ROOT_DIR

from core.utils.config import load_config, save_config, get_user_data_path
from core.nlp.command_parser import CommandParser
from core.nlp.asr_corrector import ASRCorrector

PAIRING_PATH = Path(get_user_data_path("pairing_session.json"))
VOSK_MODEL_PATH = APP_DIR / "optimized_models" / "model_vosk"
SILERO_PATH = APP_DIR / "optimized_models" / "silero_tts" / "v4_ru.pt"

dp = Dispatcher()
current_bot_instance = None
command_parser_instance = None
corrector_instance = None
vosk_model_instance = None
silero_model_instance = None

ERROR_UNREACHABLE_MSG = (
    "Я потеряла контакт с твоим ноутом 🥺\n"
    "Сигнал улетел в космос, попробуй чуть позже!"
)

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Скриншот"), KeyboardButton(text="Веб-камера")],
        [KeyboardButton(text="Статус ПК"), KeyboardButton(text="Заблокировать ПК")],
        [KeyboardButton(text="Выключить ПК")]
    ],
    resize_keyboard=True
)


def get_admin_id() -> int:
    cfg = load_config()
    return int(cfg.get("api_keys", {}).get("telegram_admin_id", 0))


def get_command_parser():
    global command_parser_instance
    if command_parser_instance is None:
        command_parser_instance = CommandParser()
    return command_parser_instance


def get_corrector():
    global corrector_instance
    if corrector_instance is None:
        corrector_instance = ASRCorrector()
    return corrector_instance


def get_vosk_model():
    global vosk_model_instance
    if vosk_model_instance is None and VOSK_MODEL_PATH.exists():
        vosk.SetLogLevel(-1)
        vosk_model_instance = vosk.Model(str(VOSK_MODEL_PATH))
    return vosk_model_instance


def get_silero_model():
    global silero_model_instance
    if silero_model_instance is None and SILERO_PATH.exists():
        try:
            torch.set_num_threads(4)
            importer = torch.package.PackageImporter(str(SILERO_PATH))
            silero_model_instance = importer.load_pickle("tts_models", "model")
            silero_model_instance.to(torch.device("cpu"))
        except Exception as e:
            print(f"[Silero Load Error]: {e}")
    return silero_model_instance


def play_audio_on_pc(text: str):
    model = get_silero_model()
    if not model or not text.strip():
        return
    try:
        cleaned = text.replace("*", "").replace("#", "").replace("`", "").strip()
        with torch.inference_mode():
            audio = model.apply_tts(text=cleaned, speaker="kseniya", sample_rate=48000)
        audio_np = audio.numpy()
        padding = np.zeros(int(48000 * 0.2), dtype=np.float32)
        audio_padded = np.concatenate([audio_np, padding])
        sd.play(audio_padded, 48000)
        sd.wait()
    except Exception as e:
        print(f"[PC Audio Error]: {e}")


def get_hardware_status() -> str:
    cpu_usage = psutil.cpu_percent(interval=0.3)
    cpu_count = psutil.cpu_count(logical=True)

    ram = psutil.virtual_memory()
    ram_used = ram.used / (1024 ** 3)
    ram_total = ram.total / (1024 ** 3)
    ram_percent = ram.percent

    disks_info = []
    seen_mounts = set()
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        mount = part.mountpoint
        if mount in seen_mounts:
            continue
        seen_mounts.add(mount)
        try:
            usage = psutil.disk_usage(mount)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            drive_clean = part.device.rstrip('\\').rstrip('/').rstrip(':')
            disks_info.append(
                f"💾 **Диск {drive_clean}:** {free_gb:.1f} ГБ свободно из {total_gb:.1f} ГБ ({usage.percent}%)"
            )
        except (PermissionError, OSError):
            continue

    disks_str = "\n".join(disks_info) if disks_info else "**Диски:** Не удалось определить"

    gpu_info = "Недоступно"
    try:
        cmd = "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
        out = subprocess.check_output(cmd, shell=True, text=True).strip()
        if out:
            parts = [p.strip() for p in out.split(",")]
            if len(parts) >= 5:
                gpu_name, temp, util, mem_used, mem_total = parts[0], parts[1], parts[2], parts[3], parts[4]
                gpu_info = f"{gpu_name}\n   Температура: {temp}°C | Нагрузка: {util}%\n   VRAM: {int(mem_used)} МБ / {int(mem_total)} МБ"
    except Exception:
        pass

    return (
        f"📊 **Текущий статус ПК:**\n\n"
        f"**Процессор:** {cpu_usage}% ({cpu_count} потоков)\n"
        f"**Оперативная память:** {ram_used:.1f} ГБ / {ram_total:.1f} ГБ ({ram_percent}%)\n"
        f"**Видеокарта:** {gpu_info}\n"
        f"{disks_str}"
    )


def transcribe_audio_file(wav_path: str) -> str:
    model = get_vosk_model()
    if not model or not os.path.exists(wav_path):
        return ""

    wf = wave.open(wav_path, "rb")
    rec = vosk.KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    results = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            part = json.loads(rec.Result())
            if part.get("text"):
                results.append(part["text"])

    final_part = json.loads(rec.FinalResult())
    if final_part.get("text"):
        results.append(final_part["text"])
    wf.close()

    raw_text = " ".join(results).strip()
    if not raw_text:
        return ""

    corrector = get_corrector()
    return corrector.correct(raw_text)


def synthesize_voice_file(text: str, output_path: str) -> bool:
    model = get_silero_model()
    if not model or not text.strip():
        return False

    try:
        cleaned = text.replace("*", "").replace("#", "").replace("`", "").strip()
        with torch.inference_mode():
            audio = model.apply_tts(text=cleaned, speaker="kseniya", sample_rate=48000)
        sf.write(output_path, audio.numpy(), 48000, format="OGG", subtype="OPUS")
        return True
    except Exception as e:
        print(f"[Voice Synthesis Error]: {e}")
        return False


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
        await message.answer("Привет-привет! Рада тебя видеть! На связи и вся во внимании. 💛", reply_markup=main_keyboard)
        return

    await message.answer("Доступ запрещен. Открой мои настройки на компьютере и отсканируй QR-код для привязки.")


@dp.message(Command("say"))
async def cmd_say(message: types.Message, command: CommandObject):
    if message.from_user.id != get_admin_id():
        return
    phrase = command.args
    if not phrase:
        await message.answer("Укажи текст, например: `/say Привет, я дома!`", parse_mode="Markdown")
        return
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, play_audio_on_pc, phrase)
    await message.answer(f"📢 Сказала на компьютере: «{phrase}»")


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


@dp.message(F.text == "Статус ПК")
async def handle_status(message: types.Message):
    if message.from_user.id != get_admin_id():
        return
    try:
        status_text = get_hardware_status()
        await message.answer(status_text, parse_mode="Markdown")
    except Exception:
        await message.answer(ERROR_UNREACHABLE_MSG)


@dp.message(F.text == "Заблокировать ПК")
async def handle_lock(message: types.Message):
    if message.from_user.id != get_admin_id():
        return
    try:
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        await message.answer("Заблокировала твой ПК 🔒")
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


@dp.message(F.voice)
async def handle_voice_message(message: types.Message, bot: Bot):
    if message.from_user.id != get_admin_id():
        return

    raw_ogg = f"temp_voice_{message.message_id}.ogg"
    wav_path = f"temp_voice_{message.message_id}.wav"
    reply_voice_path = f"temp_reply_{message.message_id}.ogg"

    try:
        file = await bot.get_file(message.voice.file_id)
        await bot.download_file(file.file_path, destination=raw_ogg)

        cmd = ["ffmpeg", "-y", "-i", raw_ogg, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        loop = asyncio.get_event_loop()
        recognized_text = await loop.run_in_executor(None, transcribe_audio_file, wav_path)

        if not recognized_text:
            await message.answer("Не смогла разобрать слова на записи 🥺")
            return

        parser = get_command_parser()
        response = await loop.run_in_executor(None, parser.process_command, recognized_text, None, True, None)

        if isinstance(response, dict):
            chat_text = response.get("chat", "") or response.get("voice", "")
            voice_text = response.get("voice", "") or chat_text
        else:
            chat_text = voice_text = str(response)

        await message.answer(f"🎤 *Распознано:* {recognized_text}\n\n💬 {chat_text}", parse_mode="Markdown")

        has_voice = await loop.run_in_executor(None, synthesize_voice_file, voice_text, reply_voice_path)
        if has_voice and os.path.exists(reply_voice_path):
            voice_file = FSInputFile(reply_voice_path)
            await message.answer_voice(voice_file)

    except Exception as e:
        print(f"[Telegram Voice Handler Error]: {e}")
        await message.answer(ERROR_UNREACHABLE_MSG)
    finally:
        for p in [raw_ogg, wav_path, reply_voice_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@dp.message(F.text)
async def handle_text_chat(message: types.Message):
    if message.from_user.id != get_admin_id():
        return

    text = message.text.strip()
    if not text:
        return

    try:
        parser = get_command_parser()
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, parser.process_command, text, None, False, None)

        if isinstance(response, dict):
            chat_text = response.get("chat", "") or response.get("voice", "")
        else:
            chat_text = str(response)

        if chat_text:
            await message.answer(chat_text)
    except Exception as e:
        print(f"[Telegram Text Handler Error]: {e}")
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