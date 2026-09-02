import asyncio
import base64
import io
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import cv2
import psutil
import pyautogui
import websockets
from PyQt6.QtCore import QThread

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from core.nlp.command_parser import CommandParser
from core.utils.config import get_user_data_path, load_config, save_config

SERVER_HOST = "185.79.139.120:8000"
PAIRING_PATH = Path(get_user_data_path("pairing_session.json"))

main_window_instance = None
command_parser_instance = None
active_ws_client = None

def get_device_uuid() -> str:
    cfg = load_config()
    dev_id = cfg.get("device_uuid")
    if not dev_id:
        dev_id = str(uuid.uuid4())
        cfg["device_uuid"] = dev_id
        save_config(cfg)
    return dev_id

def get_command_parser():
    global command_parser_instance
    if command_parser_instance is None:
        command_parser_instance = CommandParser()
    return command_parser_instance

def get_hardware_status() -> str:
    cpu_usage = psutil.cpu_percent(interval=0.3)
    cpu_count = psutil.cpu_count(logical=True)

    ram = psutil.virtual_memory()
    ram_used = ram.used / (1024**3)
    ram_total = ram.total / (1024**3)
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
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            drive_clean = part.device.rstrip("\\").rstrip("/").rstrip(":")
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

def take_screenshot_base64() -> str:
    shot = pyautogui.screenshot()
    buf = io.BytesIO()
    shot.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def take_webcam_base64() -> str:
    global main_window_instance
    frame = None

    if main_window_instance and getattr(main_window_instance, "vision_thread", None):
        if main_window_instance.vision_thread.isRunning():
            frame = main_window_instance.vision_thread.current_frame

    if frame is None:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        ret, frame_read = cap.read()
        cap.release()
        if ret and frame_read is not None:
            frame = frame_read

    if frame is not None:
        _, buffer = cv2.imencode(".png", frame)
        return base64.b64encode(buffer.tobytes()).decode("utf-8")
    return ""

def register_pairing_token(token: str, expires_at: float):
    global active_ws_client
    if active_ws_client and active_ws_client.ws and active_ws_client.loop and active_ws_client.loop.is_running():
        payload = {"action": "register_token", "token": token, "expires_at": expires_at}
        asyncio.run_coroutine_threadsafe(active_ws_client.ws.send(json.dumps(payload)), active_ws_client.loop)

def send_alert_to_server(base64_img: str, caption: str):
    global active_ws_client
    if active_ws_client and active_ws_client.ws and active_ws_client.loop and active_ws_client.loop.is_running():
        payload = {"action": "security_alert", "image_base64": base64_img, "caption": caption}
        asyncio.run_coroutine_threadsafe(active_ws_client.ws.send(json.dumps(payload)), active_ws_client.loop)

def send_text_to_server(text: str):
    global active_ws_client
    if active_ws_client and active_ws_client.ws and active_ws_client.loop and active_ws_client.loop.is_running():
        payload = {"action": "text_notification", "text": text}
        asyncio.run_coroutine_threadsafe(active_ws_client.ws.send(json.dumps(payload)), active_ws_client.loop)

class TelegramBotThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        global main_window_instance, active_ws_client
        main_window_instance = parent
        active_ws_client = self
        self.loop = None
        self.ws = None
        self._running = True

    def run(self):
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._client_loop())
        finally:
            self.loop.close()

    async def _client_loop(self):
        device_id = get_device_uuid()
        ws_url = f"ws://{SERVER_HOST}/ws/{device_id}"

        while self._running:
            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                    self.ws = ws
                    if PAIRING_PATH.exists():
                        try:
                            with open(PAIRING_PATH, "r", encoding="utf-8") as f:
                                sess = json.load(f)
                            if sess.get("status") == "pending" and time.time() < sess.get("expires_at", 0):
                                await ws.send(json.dumps({
                                    "action": "register_token",
                                    "token": sess["token"],
                                    "expires_at": sess["expires_at"]
                                }))
                        except Exception:
                            pass

                    while self._running:
                        msg_text = await ws.recv()
                        data = json.loads(msg_text)
                        await self._handle_server_message(data)

            except (websockets.ConnectionClosed, OSError):
                self.ws = None
                if not self._running: break
                await asyncio.sleep(3)
            except Exception:
                self.ws = None
                if not self._running: break
                await asyncio.sleep(3)

    async def _handle_server_message(self, data: dict):
        action = data.get("action")
        req_id = data.get("req_id")
        payload = data.get("payload", {})

        if action == "pairing_success":
            user_id = data.get("user_id")
            user_name = data.get("user_name")
            cfg = load_config()
            if "api_keys" not in cfg: cfg["api_keys"] = {}
            cfg["api_keys"]["telegram_admin_id"] = user_id
            cfg["user_name"] = user_name
            save_config(cfg)
            session_data = {"status": "paired", "user_id": user_id, "user_name": user_name}
            with open(PAIRING_PATH, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=4)
            return

        resp_payload = {}
        if action == "screenshot":
            base64_img = await self.loop.run_in_executor(None, take_screenshot_base64)
            resp_payload = {"image_base64": base64_img}
        elif action == "webcam":
            base64_img = await self.loop.run_in_executor(None, take_webcam_base64)
            resp_payload = {"image_base64": base64_img}
        elif action == "status":
            st = await self.loop.run_in_executor(None, get_hardware_status)
            resp_payload = {"text": st}
        elif action == "lock":
            subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
            resp_payload = {"text": "Заблокировала твой ПК 🔒"}
        elif action == "restart":
            subprocess.run("shutdown /r /t 5", shell=True)
            resp_payload = {"text": "Перезагружаю компьютер... 🔄"}
        elif action == "shutdown":
            subprocess.run("shutdown /s /t 5", shell=True)
            resp_payload = {"text": "Выключаю ПК. До связи! 👋"}
        elif action == "chat":
            text = payload.get("text", "")
            parser = get_command_parser()
            result = await self.loop.run_in_executor(None, parser.process_command, text, None, False, None)
            if isinstance(result, dict):
                reply_text = result.get("chat", "") or result.get("voice", "") or "Команда принята"
            else:
                reply_text = str(result)
            resp_payload = {"text": reply_text}

        if req_id and self.ws:
            answer = {"req_id": req_id, "payload": resp_payload}
            await self.ws.send(json.dumps(answer))

    def stop(self):
        self._running = False
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.wait(3000)