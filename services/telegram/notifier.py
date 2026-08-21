import os
import json
import threading
from pathlib import Path
import cv2
import requests


def _send_photo_worker(frame_or_path, caption: str, with_keyboard: bool = True):
    temp_file = None
    try:
        base_dir = Path(__file__).resolve().parent.parent.parent
        config_path = base_dir / "personal_data" / "configs" / "config.json"

        if not config_path.exists():
            return

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        token = cfg.get("api_keys", {}).get("telegram_token", "")
        admin_id = cfg.get("api_keys", {}).get("telegram_admin_id", 0)

        if not token or not admin_id:
            return

        photo_path = None
        if isinstance(frame_or_path, str):
            photo_path = frame_or_path
        elif frame_or_path is not None:
            temp_file = str(base_dir / "temp_intruder.png")
            cv2.imwrite(temp_file, frame_or_path)
            photo_path = temp_file
        else:
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()
            if ret:
                temp_file = str(base_dir / "temp_intruder.png")
                cv2.imwrite(temp_file, frame)
                photo_path = temp_file

        if photo_path and os.path.exists(photo_path):
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {"chat_id": admin_id, "caption": caption}

            if with_keyboard:
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "Заблокировать", "callback_data": "security_lock"},
                            {"text": "Не блокировать", "callback_data": "security_ignore"}
                        ]
                    ]
                }
                payload["reply_markup"] = json.dumps(reply_markup)

            with open(photo_path, "rb") as p_file:
                requests.post(
                    url,
                    data=payload,
                    files={"photo": p_file},
                    timeout=10
                )
    except Exception as e:
        print(f"[Telegram Security Alert Error]: {e}")
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


def send_security_alert(frame_or_path=None, caption="⚠️ Замечен посторонний пользователь! Заблокировать ПК?"):
    threading.Thread(target=_send_photo_worker, args=(frame_or_path, caption, True), daemon=True).start()