import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
TEMPLATE_FILE = os.path.join(BASE_DIR, "config.template.json")

DEFAULT_CONFIG = {
    "user_name": "друг",
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
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                save_config(data)
                return data
        except Exception:
            pass

    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)