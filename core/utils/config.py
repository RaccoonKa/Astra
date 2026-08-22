import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", ".."))

CONFIG_DIR = os.path.join(ROOT_DIR, "personal_data", "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
TEMPLATE_FILE = os.path.join(CONFIG_DIR, "config.template.json")

DEFAULT_CONFIG = {
    "user_name": "друг",
    "assistant_name": "Астра",
    "user_gender": "male",
    "city": "Москва",
    "autostart": False,
    "first_run": True,
    "is_configured": False,
    "music_service": "spotify",
    "use_spotify": False,
    "vpn_service": "",
    "hdrezka_domain": "https://ru1.hdreskaz.top",
    "work_apps": [
        "https://github.com"
    ],
    "rest_apps": [
        "https://youtube.com"
    ],
    "modules": {
        "vision": False,
        "gestures": False,
        "face_recognition": False,
        "eye_tracking": False,
        "telegram": False,
        "gigachat": False,
        "contacts": False,
        "memory": True
    },
    "api_keys": {
        "gigachat": "",
        "telegram_token": "",
        "telegram_admin_id": 0,
        "weather": "",
        "yandex_music_token": "",
        "spotify_client_id": "",
        "spotify_client_secret": "",
        "yandex_iot_token": ""
    }
}


def _deep_merge(default: dict, custom: dict) -> dict:
    merged = default.copy()
    for key, value in custom.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                return _deep_merge(DEFAULT_CONFIG, loaded)
        except Exception:
            pass

    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                final_cfg = _deep_merge(DEFAULT_CONFIG, data)
                save_config(final_cfg)
                return final_cfg
        except Exception:
            pass

    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(config_data: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)