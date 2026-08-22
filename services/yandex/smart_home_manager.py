import os
import json
import requests
import re


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

    def _get_stem(self, word: str) -> str:
        word = word.lower().replace("ё", "е")
        return re.sub(r'(а|я|о|е|ы|и|у|ю|ой|ей|ом|ем|ам|ям|ах|ях|ую|юю|ов|ев|ие|ый|ая|ое|ка|ки|ку|ке|кой)$', '', word)

    def _find_matching_devices(self, query: str):
        if not self.devices_cache:
            self.update_cache()

        query_clean = query.lower().replace("ё", "е").strip()
        all_words = [self._get_stem(w) for w in re.findall(r'[а-яa-z0-9]+', query_clean) if len(w) > 2]

        target_room_id = None
        target_room_name = ""
        for r_id, r_name in self.rooms_cache.items():
            r_stem = self._get_stem(r_name)
            if any(r_stem in qw or qw in r_stem for qw in all_words):
                target_room_id = r_id
                target_room_name = r_name
                break

        room_stems = [self._get_stem(target_room_name)] if target_room_name else []
        ignored_stems = {"включ", "выключ", "погас", "потуш", "зажг", "вруб", "отруб", "запуст", "астр", "пожалуйст"} | set(room_stems)

        device_stems = [w for w in all_words if w not in ignored_stems]

        is_generic_light = any(w in query_clean for w in ["свет", "все", "всё", "везде", "освещен"])
        is_lamp_specific = any(w in query_clean for w in ["ламп", "люстр", "бра", "ночник"])
        is_strip_specific = any(w in query_clean for w in ["лент", "подсветк", "диод"])
        is_garland_specific = any(w in query_clean for w in ["гирлянд", "елк", "елка"])
        is_socket_specific = any(w in query_clean for w in ["розетк", "чайник", "обогреват", "пол", "подогрев"])
        is_humidifier_specific = any(w in query_clean for w in ["увлажнител", "пар", "влажност"])

        devices_pool = self.devices_cache
        if target_room_id:
            devices_pool = [d for d in self.devices_cache if d.get("room") == target_room_id]

        specific_matches = []
        for dev in devices_pool:
            dev_name_clean = dev.get("name", "").lower().replace("ё", "е")
            dev_type = dev.get("type", "").lower()
            dev_name_stems = [self._get_stem(w) for w in re.findall(r'[а-яa-z0-9]+', dev_name_clean) if len(w) > 2]

            name_direct_match = any(ds in dev_name_stems or any(ds in dns for dns in dev_name_stems) for ds in device_stems if ds not in {"свет", "все", "всё"})

            if name_direct_match:
                specific_matches.append(dev)
                continue

            if is_lamp_specific and ("lamp" in dev_name_clean or "люстр" in dev_name_clean or "бра" in dev_name_clean) and "strip" not in dev_type:
                specific_matches.append(dev)
            elif is_strip_specific and ("strip" in dev_type or "лент" in dev_name_clean or "подсветк" in dev_name_clean):
                specific_matches.append(dev)
            elif is_garland_specific and ("гирлянд" in dev_name_clean or "елк" in dev_name_clean):
                specific_matches.append(dev)
            elif is_socket_specific and ("socket" in dev_type or "switch" in dev_type or "пол" in dev_name_clean):
                specific_matches.append(dev)
            elif is_humidifier_specific and ("humidifier" in dev_type or "увлажнител" in dev_name_clean):
                specific_matches.append(dev)

        if specific_matches:
            return specific_matches

        if target_room_id and is_generic_light:
            return [d for d in devices_pool if "light" in d.get("type", "").lower() or "lamp" in d.get("type", "").lower()]

        if not target_room_id and is_generic_light:
            return [d for d in self.devices_cache if "light" in d.get("type", "").lower() or "lamp" in d.get("type", "").lower()]

        return []

    def _find_scenario(self, query: str):
        if not self.scenarios_cache:
            self.update_cache()

        query_clean = query.lower().replace("ё", "е").strip()
        query_stems = [self._get_stem(w) for w in re.findall(r'[а-яa-z0-9]+', query_clean) if len(w) > 2]

        for sc in self.scenarios_cache:
            sc_name_clean = sc.get("name", "").lower().replace("ё", "е")
            sc_stems = [self._get_stem(w) for w in re.findall(r'[а-яa-z0-9]+', sc_name_clean) if len(w) > 2]
            if sc_name_clean in query_clean or query_clean in sc_name_clean:
                return sc
            if any(qs in ss or ss in qs for qs in query_stems for ss in sc_stems):
                return sc
        return None

    def execute_scenario_by_name(self, scenario_query: str):
        scenario = self._find_scenario(scenario_query)
        if scenario:
            return self.execute_scenario(scenario["id"], scenario["name"])
        return "Такой сценарий не найден в Умном Доме"

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