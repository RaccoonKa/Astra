import os
import threading
import base64
import cv2
from services.telegram.telegram_bot import send_alert_to_server, send_text_to_server

def _send_photo_worker(frame_or_path, caption: str):
    try:
        base64_img = ""
        if isinstance(frame_or_path, str) and os.path.exists(frame_or_path):
            with open(frame_or_path, "rb") as f:
                base64_img = base64.b64encode(f.read()).decode("utf-8")
        elif frame_or_path is not None:
            _, buffer = cv2.imencode(".png", frame_or_path)
            base64_img = base64.b64encode(buffer.tobytes()).decode("utf-8")
        else:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            ret, frame = cap.read()
            cap.release()
            if ret:
                _, buffer = cv2.imencode(".png", frame)
                base64_img = base64.b64encode(buffer.tobytes()).decode("utf-8")

        if base64_img:
            send_alert_to_server(base64_img, caption)
    except Exception as e:
        print(f"[Notifier Error]: {e}")

def send_security_alert(frame_or_path=None, caption="⚠️ Внимание! Замечен посторонний пользователь. Заблокировать ПК?"):
    threading.Thread(target=_send_photo_worker, args=(frame_or_path, caption), daemon=True).start()

def send_telegram_notification(text: str):
    threading.Thread(target=send_text_to_server, args=(text,), daemon=True).start()