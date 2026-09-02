import asyncio
import json
import base64
import time
import aiosqlite
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile

BOT_TOKEN = ""
DB_PATH = "/root/astra_hub/hub.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = dp

active_connections: dict[str, WebSocket] = {}
pending_responses: dict[str, asyncio.Future] = {}

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Скриншот"), KeyboardButton(text="Веб-камера")],
        [KeyboardButton(text="Статус ПК"), KeyboardButton(text="Заблокировать ПК")],
        [KeyboardButton(text="Перезагрузить ПК"), KeyboardButton(text="Выключить ПК")]
    ],
    resize_keyboard=True
)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pairings (
                device_uuid TEXT PRIMARY KEY,
                user_id INTEGER,
                user_name TEXT,
                paired_at REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_tokens (
                token TEXT PRIMARY KEY,
                device_uuid TEXT,
                expires_at REAL
            )
        """)
        await db.commit()

async def get_device_by_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT device_uuid FROM pairings WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

@router.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    token = command.args
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "друг"

    if token:
        token = token.strip()
        now = time.time()
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT device_uuid FROM pending_tokens WHERE token = ? AND expires_at > ?", (token, now)) as cur:
                row = await cur.fetchone()
                if row:
                    device_uuid = row[0]
                    await db.execute(
                        "INSERT OR REPLACE INTO pairings (device_uuid, user_id, user_name, paired_at) VALUES (?, ?, ?, ?)",
                        (device_uuid, user_id, user_name, now)
                    )
                    await db.execute("DELETE FROM pending_tokens WHERE token = ?", (token,))
                    await db.commit()

                    if device_uuid in active_connections:
                        await active_connections[device_uuid].send_text(json.dumps({
                            "action": "pairing_success",
                            "user_id": user_id,
                            "user_name": user_name
                        }))

                    await message.answer(f"ПК успешно привязан к профилю {user_name}! ✨", reply_markup=main_keyboard)
                    return
                else:
                    await message.answer("Срок действия кода истек или он недействителен.")
                    return

    device = await get_device_by_user(user_id)
    if device:
        await message.answer("С возвращением! Управление активно. 💛", reply_markup=main_keyboard)
    else:
        await message.answer("Устройство не привязано. Открой настройки Астры на ПК и нажми 'Привязать'.")

async def forward_command_to_pc(user_id: int, action: str, payload: dict = None) -> dict:
    device_uuid = await get_device_by_user(user_id)
    if not device_uuid or device_uuid not in active_connections:
        return {"error": "Компьютер не в сети или Астра выключена."}

    req_id = f"{action}_{int(time.time() * 1000)}"
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_responses[req_id] = future

    msg = {"req_id": req_id, "action": action, "payload": payload or {}}
    try:
        await active_connections[device_uuid].send_text(json.dumps(msg))
        result = await asyncio.wait_for(future, timeout=30.0)
        return result
    except asyncio.TimeoutError:
        return {"error": "Таймаут ожидания ответа от ПК."}
    finally:
        pending_responses.pop(req_id, None)

@router.message(F.text.in_({"Скриншот", "Веб-камера", "Статус ПК", "Заблокировать ПК", "Перезагрузить ПК", "Выключить ПК"}))
async def handle_buttons(message: types.Message):
    cmd_map = {
        "Скриншот": "screenshot",
        "Веб-камера": "webcam",
        "Статус ПК": "status",
        "Заблокировать ПК": "lock",
        "Перезагрузить ПК": "restart",
        "Выключить ПК": "shutdown"
    }
    action = cmd_map[message.text]
    res = await forward_command_to_pc(message.from_user.id, action)

    if "error" in res:
        await message.answer(f"❌ {res['error']}")
        return

    if action in ("screenshot", "webcam"):
        img_bytes = base64.b64decode(res["image_base64"])
        caption = "Рабочий стол" if action == "screenshot" else "Снимок с веб-камеры 📷"
        file = BufferedInputFile(img_bytes, filename=f"{action}.png")
        await message.answer_photo(file, caption=caption)
    elif action == "status":
        await message.answer(res.get("text", "Статус получен."), parse_mode="Markdown")
    else:
        await message.answer(res.get("text", "Команда выполнена."))

@router.message(F.text)
async def handle_chat_text(message: types.Message):
    res = await forward_command_to_pc(message.from_user.id, "chat", {"text": message.text})
    if "error" in res:
        await message.answer(f"❌ {res['error']}")
    else:
        await message.answer(res.get("text", "Готово."))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    polling_task.cancel()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws/{device_uuid}")
async def websocket_endpoint(websocket: WebSocket, device_uuid: str):
    await websocket.accept()
    active_connections[device_uuid] = websocket
    print(f"[WS Connect]: ПК {device_uuid} подключен.")
    try:
        while True:
            data_raw = await websocket.receive_text()
            data = json.loads(data_raw)

            if data.get("action") == "register_token":
                token = data["token"]
                expires_at = data["expires_at"]
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "INSERT OR REPLACE INTO pending_tokens (token, device_uuid, expires_at) VALUES (?, ?, ?)",
                        (token, device_uuid, expires_at)
                    )
                    await db.commit()
                continue

            req_id = data.get("req_id")
            if req_id and req_id in pending_responses:
                pending_responses[req_id].set_result(data.get("payload", {}))

    except WebSocketDisconnect:
        active_connections.pop(device_uuid, None)
        print(f"[WS Disconnect]: ПК {device_uuid} отключился.")

if __name__ == "__main__":
    uvicorn.run("tg_server:app", host="0.0.0.0", port=8000)