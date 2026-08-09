import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "user_name": "Светозар",
    "assistant_name": "Астра",
    "autostart": False,
    "modules": {
        "vision": True,
        "telegram": False,
        "gigachat": False,
        "contacts": False
    },
    "api_keys": {
        "gigachat": "",
        "telegram_token": "",
        "weather": ""
    }
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)