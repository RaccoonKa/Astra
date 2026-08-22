import os
import time
import psutil
import ctypes
import re
from core.utils.config import load_config


class ZapretManager:
    STRATEGIES = [
        "general (ALT).bat",
        "general (ALT2).bat",
        "general (ALT3).bat",
        "general (ALT4).bat",
        "general (ALT5).bat",
        "general (ALT6).bat",
        "general (ALT7).bat",
        "general (ALT8).bat",
        "general (ALT9).bat",
        "general (ALT10).bat",
        "general (ALT11).bat",
        "general (ALT12).bat",
        "general (FAKE TLS AUTO ALT).bat",
        "general (FAKE TLS AUTO ALT2).bat",
        "general (FAKE TLS AUTO ALT3).bat",
        "general (FAKE TLS AUTO).bat",
        "general (SIMPLE FAKE ALT).bat",
        "general (SIMPLE FAKE ALT2).bat",
        "general (SIMPLE FAKE).bat",
        "general.bat"
    ]

    def __init__(self):
        self.process_name = "winws.exe"

    def _find_zapret_dir(self):
        cfg = load_config()
        custom_path = cfg.get("zapret_path", "") or cfg.get("paths", {}).get("zapret", "")
        if custom_path and os.path.exists(custom_path):
            if os.path.isdir(custom_path):
                if any(os.path.exists(os.path.join(custom_path, s)) for s in self.STRATEGIES):
                    return custom_path
                parent = os.path.dirname(custom_path)
                if any(os.path.exists(os.path.join(parent, s)) for s in self.STRATEGIES):
                    return parent
                return custom_path
            return os.path.dirname(custom_path)

        user_home = os.path.expanduser("~")
        search_dirs = [
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Documents"),
            r"C:\zapret",
            r"C:\zapret-winws",
            r"C:\zapret-discord-youtube-main",
            r"D:\zapret",
            r"D:\zapret-winws",
            r"D:\zapret-discord-youtube-main",
            r"C:\Program Files\zapret",
            r"C:\Program Files (x86)\zapret",
            r"C:",
            r"D:"
        ]

        for s_dir in search_dirs:
            if not os.path.exists(s_dir):
                continue
            try:
                for root, dirs, files in os.walk(s_dir):
                    if "general (ALT).bat" in files or "service.bat" in files or "general.bat" in files:
                        return root
                    if "winws.exe" in files:
                        parent = os.path.dirname(root)
                        if any(os.path.exists(os.path.join(parent, s)) for s in self.STRATEGIES):
                            return parent
            except Exception:
                continue

        return None

    def _prepare_silent_bat(self, bat_path, zapret_dir):
        content = ""
        for enc in ["utf-8", "cp1251", "cp866", "latin-1"]:
            try:
                with open(bat_path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except Exception:
                continue

        if not content:
            return bat_path

        lines = content.splitlines()
        cleaned = ["@echo off", "chcp 65001 >nul", f'cd /d "{zapret_dir}"']

        for line in lines:
            line_strip = line.strip()
            line_low = line_strip.lower()

            if "check_updates" in line_low:
                continue
            if line_low.startswith("pause") or line_low.startswith("timeout"):
                continue
            if line_low.startswith("@echo off") or line_low.startswith("cd /d") or line_low.startswith("chcp"):
                continue

            if "winws.exe" in line_low and "start " in line_low:
                match = re.search(r'("[^"]*winws\.exe".*|[^ \t]*winws\.exe.*)', line_strip, flags=re.IGNORECASE)
                if match:
                    line_strip = match.group(1)

            cleaned.append(line_strip)

        silent_bat_path = os.path.join(zapret_dir, "_astra_run.bat")
        try:
            with open(silent_bat_path, "w", encoding="cp1251", errors="ignore") as f:
                f.write("\n".join(cleaned))
            return silent_bat_path
        except Exception:
            return bat_path

    def get_strategies_menu(self):
        lines = [f"{i + 1}. {name}" for i, name in enumerate(self.STRATEGIES)]
        return "\n".join(lines)

    def is_running(self):
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == self.process_name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def start_strategy_by_index(self, index: int):
        if index < 1 or index > len(self.STRATEGIES):
            return "Неверный номер обхода. Выбери от 1 до 20."

        target_bat_name = self.STRATEGIES[index - 1]
        zapret_dir = self._find_zapret_dir()

        if not zapret_dir:
            return "Не удалось найти папку с Запретом."

        bat_path = os.path.join(zapret_dir, target_bat_name)
        if not os.path.exists(bat_path):
            parent = os.path.dirname(zapret_dir)
            alt_path = os.path.join(parent, target_bat_name)
            if os.path.exists(alt_path):
                bat_path = alt_path
                zapret_dir = parent
            else:
                return f"Файл {target_bat_name} не найден в папке."

        self.stop()
        time.sleep(0.1)

        runner_bat = self._prepare_silent_bat(bat_path, zapret_dir)

        try:
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "cmd.exe",
                f'/c "{runner_bat}"',
                zapret_dir,
                0
            )
        except Exception as e:
            return f"Ошибка при запуске: {e}"

        for _ in range(15):
            time.sleep(0.15)
            if self.is_running():
                time.sleep(0.8)
                if self.is_running():
                    return f"Запустила #{index}: {target_bat_name}"
                else:
                    return f"Процесс запустился, но сразу закрылся (возможна ошибка параметров или порт занят)."

        return f"Не удалось запустить #{index}: процесс winws не поднялся."

    def start(self):
        return self.start_strategy_by_index(18)

    def stop(self):
        killed_any = False
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == self.process_name:
                    proc.kill()
                    killed_any = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if killed_any:
            return "Выключила Запрет"
        return "Запрет уже выключен"