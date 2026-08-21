import os
import re
import json
from services.vpn.adapters.core_adapter import CoreAdapter
from services.vpn.adapters.gui_adapter import GuiAdapter


class VpnManager:
    VPN_ALIASES = {
        "sota": [
            "сота", "sota", "соту", "соте", "сотой", "соты", "сотовый", "свет",
            "sota vpn", "sota connect", "сота впн", "соту впн", "соте впн",
            "сото", "сома", "сона", "сопа", "с0та", "сота вп", "соточка",
            "сотка", "соты впн", "сота коннект", "сота соединение",
            "сота интернет"
        ],
        "happ": [
            "happ", "хапп", "хэпп", "хепп", "хап", "хэп", "хеп", "хат",
            "хаппа", "хаппе", "хаппом", "хаппу", "happ vpn", "хапп впн", "хэпп впн",
            "хаб", "хабб", "хаппи", "хэппи", "хепи", "хапи", "хап впн",
            "хэп впн", "хеп впн", "хапп соединение", "хапп интернет",
            "хапп сервис"
        ],
        "v2ray": [
            "v2ray", "xray", "в2рей", "в2рай", "иксрей", "ви ту рэй", "ви ту рей",
            "виту рэй", "витурей", "витурэй", "v2ray vpn", "в2рей впн",
            "втурай", "втурэй", "витурай", "витурэй", "виту рай",
            "виту рей", "витурай впн", "витурэй впн", "втурея",
            "втурей", "втурый"
        ],
        "wireguard": [
            "wireguard", "вайргард", "вирегуард", "варгвард", "варгард", "варгарт",
            "вайргарда", "вайргарду", "вайргардом", "wireguard vpn",
            "вайргард впн", "вайргард сервис", "вайргард подключение",
            "вайргард интернет", "вайргуард", "вайргвард", "вайргарт",
            "вайргорд", "виргард", "виргуард", "вайргард соединение"
        ]
    }

    GENERIC_VPN_TRIGGERS = [
        "впн", "vpn", "вэ пэ эн", "вэпээн", "випиэн", "ви пи эн", "впээн", "вэпэн",
        "вэпээн", "випиэн", "вэпэн", "випэн", "впнн", "вппн", "ввпн", "впм",
        "вбн", "фпн", "впэен", "впиэн"
    ]

    def __init__(self):
        self.core = CoreAdapter()
        self.gui = GuiAdapter()
        self.last_active_vpn = None

    def _get_config_path(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, "personal_data", "configs", "config.json")

    def get_configured_vpn(self) -> str:
        cfg_path = self._get_config_path()
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return cfg.get("vpn_service", "none").lower()
            except Exception:
                pass
        return "none"

    def set_configured_vpn(self, vpn_type: str):
        cfg_path = self._get_config_path()
        cfg_data = {}
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
            except Exception:
                pass
        cfg_data["vpn_service"] = vpn_type
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[VpnManager Save Error]: {e}")

    def parse_vpn_name(self, text: str) -> str:
        text_low = text.lower().strip()
        for vpn_key, triggers in self.VPN_ALIASES.items():
            for trig in triggers:
                pattern = r'\b' + re.escape(trig) + r'\b' if ' ' not in trig else re.escape(trig)
                if re.search(pattern, text_low):
                    return vpn_key
        return "none"

    def is_generic_vpn_mention(self, text: str) -> bool:
        text_low = text.lower().strip()
        return any(re.search(r'\b' + re.escape(w) + r'\b', text_low) for w in self.GENERIC_VPN_TRIGGERS)

    def connect(self, specific_vpn: str = None) -> str:
        target = specific_vpn or self.get_configured_vpn()

        if target == "sota":
            res = self.gui.connect_sota()
            self.last_active_vpn = "sota"
            return res
        elif target == "happ":
            res = self.gui.connect_happ()
            self.last_active_vpn = "happ"
            return res
        elif target == "v2ray":
            res = self.core.connect_v2ray("C:\\v2ray\\v2ray.exe")
            self.last_active_vpn = "v2ray"
            return res
        elif target == "wireguard":
            res = self.core.connect_wireguard()
            self.last_active_vpn = "wireguard"
            return res
        else:
            return "none"

    def disconnect(self, specific_vpn: str = None) -> str:
        target = specific_vpn or self.last_active_vpn or self.get_configured_vpn()

        if target == "sota":
            res = self.gui.disconnect_sota()
            self.last_active_vpn = None
            return res
        elif target == "happ":
            res = self.gui.disconnect_happ()
            self.last_active_vpn = None
            return res
        elif target == "v2ray":
            res = self.core.disconnect_v2ray()
            self.last_active_vpn = None
            return res
        elif target == "wireguard":
            res = self.core.disconnect_wireguard()
            self.last_active_vpn = None
            return res
        else:
            return "none"