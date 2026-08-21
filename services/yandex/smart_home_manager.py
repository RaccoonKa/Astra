import os
import json
import requests


class SmartHomeManager:
    API_URL = "https://api.iot.yandex.net/v1.0"

    def __init__(self):
        self.devices_cache = []
        self.scenarios_cache = []
        self.rooms_cache = {}

    def _get_token(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "personal_data", "configs", "config.json")
        template_path = os.path.join(base_dir, "personal_data", "configs", "config.template.json")
        target_path = config_path if os.path.exists(config_path) else template_path

        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    keys = cfg.get("api_keys", {})
                    return keys.get("yandex_iot_token") or keys.get("yandex_token") or keys.get("yandex_music", "")
            except Exception:
                pass
        return ""

    def _get_headers(self):
        token = self._get_token()
        if not token:
            return None
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def update_cache(self):
        headers = self._get_headers()
        if not headers:
            return False, "Укажи токен Яндекса в настройках"

        try:
            res = requests.get(f"{self.API_URL}/user/info", headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                self.devices_cache = data.get("devices", [])
                self.scenarios_cache = data.get("scenarios", [])
                rooms = data.get("rooms", [])
                self.rooms_cache = {r["id"]: r["name"].lower() for r in rooms}
                return True, "Данные обновлены"
            elif res.status_code == 401:
                return False, "Неверный или просроченный токен Яндекса"
            return False, f"Ошибка API: {res.status_code}"
        except Exception as e:
            return False, f"Не удалось связаться с умным домом: {e}"

    def _find_matching_devices(self, query):
        if not self.devices_cache:
            self.update_cache()

        query_clean = query.lower().strip()
        matched = []

        is_light_query = any(w in query_clean for w in ["свет", "люстр", "ламп", "бра", "ночник", "подсветк", "диод"])
        is_socket_query = any(w in query_clean for w in ["розетк", "чайник", "обогреват", "удлинител", "питани"])

        for dev in self.devices_cache:
            dev_name = dev.get("name", "").lower()
            dev_type = dev.get("type", "").lower()
            room_name = self.rooms_cache.get(dev.get("room"), "")

            if query_clean in dev_name or dev_name in query_clean:
                matched.append(dev)
                continue

            if room_name and room_name in query_clean:
                if is_light_query and ("light" in dev_type or "lamp" in dev_type):
                    matched.append(dev)
                elif is_socket_query and ("socket" in dev_type or "switch" in dev_type):
                    matched.append(dev)
                elif not is_light_query and not is_socket_query:
                    matched.append(dev)
                continue

            if is_light_query and ("light" in dev_type or "lamp" in dev_type):
                if not any(r in query_clean for r in self.rooms_cache.values()):
                    matched.append(dev)
            elif is_socket_query and ("socket" in dev_type or "switch" in dev_type):
                if not any(r in query_clean for r in self.rooms_cache.values()):
                    matched.append(dev)

        return matched

    def _find_scenario(self, query):
        if not self.scenarios_cache:
            self.update_cache()

        query_clean = query.lower().strip()
        for sc in self.scenarios_cache:
            name = sc.get("name", "").lower()
            if name in query_clean or query_clean in name:
                return sc
        return None

    def turn_on(self, target_query=""):
        headers = self._get_headers()
        if not headers:
            return "Укажи токен умного дома в настройках"

        scenario = self._find_scenario(target_query)
        if scenario:
            return self.execute_scenario(scenario["id"], scenario["name"])

        devices = self._find_matching_devices(target_query if target_query else "свет")
        if not devices:
            self.update_cache()
            devices = self._find_matching_devices(target_query if target_query else "свет")

        if not devices:
            return "Не нашла подходящих устройств"

        actions_payload = []
        for dev in devices:
            for cap in dev.get("capabilities", []):
                if cap.get("type") == "devices.capabilities.on_off":
                    actions_payload.append({
                        "id": dev["id"],
                        "actions": [{
                            "type": "devices.capabilities.on_off",
                            "state": {"instance": "on", "value": True}
                        }]
                    })
                    break

        if not actions_payload:
            return "Устройство не поддерживает включение"

        try:
            res = requests.post(
                f"{self.API_URL}/devices/actions",
                headers=headers,
                json={"devices": actions_payload},
                timeout=5
            )
            if res.status_code == 200:
                return "Включила!"
            return "Не удалось отправить команду на устройство"
        except Exception:
            return "Ошибка связи с умным домом"

    def turn_off(self, target_query=""):
        headers = self._get_headers()
        if not headers:
            return "Укажи токен умного дома в настройках"

        devices = self._find_matching_devices(target_query if target_query else "свет")
        if not devices:
            self.update_cache()
            devices = self._find_matching_devices(target_query if target_query else "свет")

        if not devices:
            return "Не нашла подходящих устройств"

        actions_payload = []
        for dev in devices:
            for cap in dev.get("capabilities", []):
                if cap.get("type") == "devices.capabilities.on_off":
                    actions_payload.append({
                        "id": dev["id"],
                        "actions": [{
                            "type": "devices.capabilities.on_off",
                            "state": {"instance": "on", "value": False}
                        }]
                    })
                    break

        if not actions_payload:
            return "Устройство не поддерживает выключение"

        try:
            res = requests.post(
                f"{self.API_URL}/devices/actions",
                headers=headers,
                json={"devices": actions_payload},
                timeout=5
            )
            if res.status_code == 200:
                return "Выключила!"
            return "Не удалось отправить команду на устройство"
        except Exception:
            return "Ошибка связи с умным домом"

    def set_brightness(self, brightness_val, target_query=""):
        headers = self._get_headers()
        if not headers:
            return "Укажи токен умного дома в настройках"

        val = max(1, min(100, int(brightness_val)))
        devices = self._find_matching_devices(target_query if target_query else "свет")

        if not devices:
            return "Не нашла лампы для изменения яркости"

        actions_payload = []
        for dev in devices:
            for cap in dev.get("capabilities", []):
                if cap.get("type") == "devices.capabilities.range" and cap.get("parameters", {}).get("instance") == "brightness":
                    actions_payload.append({
                        "id": dev["id"],
                        "actions": [{
                            "type": "devices.capabilities.range",
                            "state": {"instance": "brightness", "value": val}
                        }]
                    })
                    break

        if not actions_payload:
            return "Устройство не поддерживает регулировку яркости"

        try:
            res = requests.post(
                f"{self.API_URL}/devices/actions",
                headers=headers,
                json={"devices": actions_payload},
                timeout=5
            )
            if res.status_code == 200:
                return f"Яркость {val} процентов"
            return "Не удалось изменить яркость"
        except Exception:
            return "Ошибка связи с умным домом"

    def execute_scenario(self, scenario_id, scenario_name=""):
        headers = self._get_headers()
        if not headers:
            return "Укажи токен умного дома в настройках"

        try:
            res = requests.post(
                f"{self.API_URL}/scenarios/{scenario_id}/actions",
                headers=headers,
                timeout=5
            )
            if res.status_code == 200:
                return f"Сценарий {scenario_name} запущен" if scenario_name else "Сценарий выполнен"
            return "Не удалось активировать сценарий"
        except Exception:
            return "Ошибка связи с умным домом"