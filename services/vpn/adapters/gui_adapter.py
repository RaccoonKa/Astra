import os
import sys
import time
import subprocess
import ctypes
from ctypes import wintypes
import psutil
import cv2
import numpy as np
from PIL import ImageGrab
import pyautogui
import winreg
import shutil

pyautogui.FAILSAFE = False


class GuiAdapter:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            base_app = os.path.dirname(sys.executable)
            cand1 = os.path.join(base_app, "services", "vpn", "templates")
            cand2 = os.path.join(base_app, "templates")
            self.templates_dir = cand1 if os.path.exists(cand1) else cand2
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.templates_dir = os.path.join(self.base_dir, "templates")

        self._cached_sota_target = None
        self._cached_happ_target = None

    def _get_system_scale(self) -> int:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            return int(round(dpi / 96.0 * 100))
        except Exception:
            return 100

    def _get_closest_scale_folder(self) -> str:
        if not os.path.exists(self.templates_dir):
            return "100"

        available_scales = []
        for entry in os.listdir(self.templates_dir):
            full_path = os.path.join(self.templates_dir, entry)
            if os.path.isdir(full_path) and entry.isdigit():
                available_scales.append(int(entry))

        if not available_scales:
            return "100"

        current_scale = self._get_system_scale()
        closest = min(available_scales, key=lambda s: abs(s - current_scale))
        return str(closest)

    def _collect_template_paths(self, app_name: str, subfolder: str = "") -> list:
        scale_folder = self._get_closest_scale_folder()
        app_dir = os.path.join(self.templates_dir, scale_folder, app_name)

        if subfolder:
            app_dir = os.path.join(app_dir, subfolder)

        if not os.path.exists(app_dir):
            return []

        template_paths = []
        for root, _, files in os.walk(app_dir):
            for file in files:
                if file.lower().endswith(".png"):
                    template_paths.append(os.path.join(root, file))

        return template_paths

    def _find_best_match(self, template_paths: list, hwnd: int = 0, threshold: float = 0.78, bottom_only: bool = False):
        if not template_paths:
            return None

        offset_x, offset_y = 0, 0
        grab_success = False
        screen = None

        if hwnd and ctypes.windll.user32.IsWindow(hwnd):
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 100 and h > 100:
                try:
                    if bottom_only:
                        top_bound = rect.bottom - int(h * 0.28)
                        bbox = (rect.left, top_bound, rect.right, rect.bottom)
                        offset_x, offset_y = rect.left, top_bound
                    else:
                        bbox = (rect.left, rect.top, rect.right, rect.bottom)
                        offset_x, offset_y = rect.left, rect.top

                    screen = np.array(ImageGrab.grab(bbox=bbox))
                    grab_success = True
                except Exception:
                    grab_success = False

        if not grab_success or screen is None:
            screen = np.array(ImageGrab.grab())
            offset_x, offset_y = 0, 0

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)

        best_score = -1.0
        best_coords = None

        for tpl_path in template_paths:
            template = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue

            th, tw = template.shape[:2]
            if screen_gray.shape[0] < th or screen_gray.shape[1] < tw:
                continue

            res = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_score:
                best_score = max_val
                best_coords = (offset_x + max_loc[0] + tw // 2, offset_y + max_loc[1] + th // 2)

        if best_score >= threshold and best_coords is not None:
            return best_coords

        return None

    def _safe_click(self, x, y):
        """Безопасный клик с задержкой, чтобы избежать ложных двойных кликов во Flutter"""
        pyautogui.mouseDown(x, y)
        time.sleep(0.08)
        pyautogui.mouseUp(x, y)

    def click_app_toggle(self, app_name: str, hwnd: int = 0, retries: int = 8, delay: float = 0.15,
                         threshold: float = 0.78, bottom_only: bool = False) -> bool:
        template_paths = self._collect_template_paths(app_name)
        if not template_paths:
            return False

        for _ in range(retries):
            coords = self._find_best_match(template_paths, hwnd=hwnd, threshold=threshold, bottom_only=bottom_only)
            if coords:
                self._safe_click(coords[0], coords[1])
                time.sleep(0.2)
                return True
            time.sleep(delay)

        return False

    def _get_window_hwnd(self, title_keywords: list, process_names: list = None) -> int:
        candidates = []

        def enum_windows_proc(hwnd, extra):
            if not ctypes.windll.user32.IsWindow(hwnd):
                return True

            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            window_title = buff.value.strip().lower()

            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            is_visible = bool(ctypes.windll.user32.IsWindowVisible(hwnd))

            matched = False
            if any(kw.lower() in window_title for kw in title_keywords):
                matched = True
            elif process_names:
                lpdw_pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
                try:
                    p = psutil.Process(lpdw_pid.value)
                    p_name = p.name().lower()
                    if any(pn.lower() in p_name for pn in process_names):
                        matched = True
                except Exception:
                    pass

            if matched:
                score = 0
                if is_visible:
                    score += 20
                if w > 150 and h > 150:
                    score += 20
                if length > 0:
                    score += 10
                candidates.append((score, hwnd))

            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return 0

    def _show_and_focus(self, hwnd: int):
        if hwnd and ctypes.windll.user32.IsWindow(hwnd):
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
            time.sleep(0.2)

    def _minimize(self, hwnd: int):
        if hwnd and ctypes.windll.user32.IsWindow(hwnd):
            time.sleep(0.2)
            ctypes.windll.user32.ShowWindow(hwnd, 6)

    def _get_path_from_uninstall_registry(self, target_name: str) -> str:
        paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        ]
        for hkey, path in paths:
            try:
                with winreg.OpenKey(hkey, path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if target_name.lower() in display_name.lower():
                                    try:
                                        install_loc, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                        if install_loc:
                                            exe_path = os.path.join(install_loc, f"{target_name}.exe")
                                            if os.path.exists(exe_path):
                                                return exe_path
                                    except OSError:
                                        pass
                                    try:
                                        display_icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                        if display_icon:
                                            clean_path = display_icon.strip('"').split(',')[0]
                                            if clean_path.lower().endswith(".exe") and os.path.exists(clean_path):
                                                return clean_path
                                    except OSError:
                                        pass
                        except OSError:
                            continue
            except OSError:
                continue
        return ""

    def _get_path_from_protocol_registry(self, protocol_name: str) -> str:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{protocol_name}\shell\open\command") as key:
                cmd, _ = winreg.QueryValueEx(key, "")
                import re
                match = re.search(r'"([^"]+\.exe)"', cmd, re.IGNORECASE)
                if match and os.path.exists(match.group(1)):
                    return match.group(1)
        except Exception:
            pass
        return ""

    def _find_target_executable(self, exact_name: str, name_keywords: list) -> str:
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                p_name = (proc.info.get('name') or '').lower()
                if p_name == exact_name.lower():
                    exe_path = proc.info.get('exe')
                    if exe_path and os.path.exists(exe_path):
                        return exe_path
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("PROGRAMFILES", "")
        prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")
        user_profile = os.environ.get("USERPROFILE", "")
        public_profile = os.environ.get("PUBLIC", r"C:\Users\Public")

        shortcut_dirs = [
            os.path.join(user_profile, "Desktop"),
            os.path.join(public_profile, "Desktop")
        ]

        for s_dir in shortcut_dirs:
            if os.path.exists(s_dir):
                for root, _, files in os.walk(s_dir):
                    for f in files:
                        f_low = f.lower()
                        if any(kw in f_low for kw in name_keywords) and f_low.endswith(".lnk"):
                            return os.path.join(root, f)

        search_roots = [
            os.path.join(localappdata, "Programs"),
            localappdata,
            appdata,
            prog_files,
            prog_files_x86
        ]

        for s_root in search_roots:
            if not s_root or not os.path.exists(s_root):
                continue
            try:
                entries = os.listdir(s_root)
            except Exception:
                continue

            for entry in entries:
                entry_low = entry.lower()
                if any(kw in entry_low for kw in name_keywords):
                    full_entry_dir = os.path.join(s_root, entry)
                    if os.path.isdir(full_entry_dir):
                        try:
                            for root, _, files in os.walk(full_entry_dir):
                                for f in files:
                                    if f.lower() == exact_name.lower():
                                        return os.path.join(root, f)
                        except Exception:
                            pass

        return ""

    def _find_sota_target(self) -> str:
        if self._cached_sota_target and os.path.exists(self._cached_sota_target):
            return self._cached_sota_target

        reg_path = self._get_path_from_uninstall_registry("Sota") or self._get_path_from_protocol_registry("sota")
        if reg_path:
            self._cached_sota_target = reg_path
            return reg_path

        target = self._find_target_executable("sota connect.exe", ["sota", "interhive"])
        if not target:
            target = self._find_target_executable("sota.exe", ["sota", "interhive"])

        if not target:
            target = shutil.which("sota connect.exe") or shutil.which("sota.exe")

        if target:
            self._cached_sota_target = target
        return target or ""

    def _find_happ_target(self) -> str:
        if self._cached_happ_target and os.path.exists(self._cached_happ_target):
            return self._cached_happ_target

        reg_path = self._get_path_from_uninstall_registry("Happ") or self._get_path_from_protocol_registry("happ")
        if reg_path:
            self._cached_happ_target = reg_path
            return reg_path

        target = self._find_target_executable("happ.exe", ["happ", "хапп"])

        if not target:
            target = shutil.which("happ.exe")

        if target:
            self._cached_happ_target = target
        return target or ""

    def _launch_target(self, target_path: str):
        try:
            os.startfile(target_path)
        except Exception:
            work_dir = os.path.dirname(target_path)
            subprocess.Popen(f'"{target_path}"', cwd=work_dir, shell=True)

    def connect_sota(self):
        return self.toggle_sota()

    def disconnect_sota(self):
        return self.toggle_sota()

    def toggle_sota(self):
        try:
            hwnd = self._get_window_hwnd(["Sota Connect", "Sota"],
                                         ["sota connect.exe", "sotaconnect.exe", "sota.exe", "sotaconnectclient.exe"])

            if not hwnd:
                target_path = self._find_sota_target()
                if target_path:
                    self._launch_target(target_path)
                    for _ in range(15):
                        time.sleep(0.25)
                        hwnd = self._get_window_hwnd(["Sota Connect", "Sota"],
                                                     ["sota connect.exe", "sotaconnect.exe", "sota.exe",
                                                      "sotaconnectclient.exe"])
                        if hwnd:
                            break
                else:
                    return "Не удалось найти путь к приложению Сота"

            self._show_and_focus(hwnd)

            if self.click_app_toggle("sota_connect", hwnd=hwnd, threshold=0.72):
                self._minimize(hwnd)
                return "Сделала!"

            return "Открыла Соту"
        except Exception as e:
            return f"Не удалось запустить Соту: {e}"

    def connect_happ(self):
        return self._set_happ_state(target_state=True)

    def disconnect_happ(self):
        return self._set_happ_state(target_state=False)

    def _set_happ_state(self, target_state: bool):
        try:
            target_path = self._find_happ_target()
            if not target_path:
                return "Не удалось найти приложение Happ.exe."

            hwnd = self._get_window_hwnd(["Happ"], ["happ.exe"])
            was_launched = False

            if not hwnd or not ctypes.windll.user32.IsWindowVisible(hwnd):
                self._launch_target(target_path)
                was_launched = True

            for _ in range(25):
                time.sleep(0.3)
                hwnd = self._get_window_hwnd(["Happ"], ["happ.exe"])
                if hwnd and ctypes.windll.user32.IsWindowVisible(hwnd):
                    break

            if not hwnd:
                return "Не удалось дождаться открытия окна Хапп"

            self._show_and_focus(hwnd)
            time.sleep(1.2 if was_launched else 0.4)

            desired_folder = "disabled" if target_state else "active"
            opposite_folder = "active" if target_state else "disabled"

            # Защита от альцгеймера екарный бабай
            opposite_templates = self._collect_template_paths("happ", subfolder=opposite_folder)
            if opposite_templates:
                if self._find_best_match(opposite_templates, hwnd=hwnd, threshold=0.75):
                    self._minimize(hwnd)
                    return "Хапп уже " + ("включен!" if target_state else "выключен!")

            desired_templates = self._collect_template_paths("happ", subfolder=desired_folder)

            if not desired_templates:
                desired_templates = self._collect_template_paths("happ")

            for _ in range(8):
                coords = self._find_best_match(desired_templates, hwnd=hwnd, threshold=0.75)
                if coords:
                    self._safe_click(coords[0], coords[1])
                    time.sleep(0.3)
                    self._minimize(hwnd)
                    return "Включила Хапп!" if target_state else "Выключила Хапп!"
                time.sleep(0.25)

            self._minimize(hwnd)
            return "Открыла Хапп, но не смогла распознать нужную кнопку"

        except Exception as e:
            return f"Не удалось управлять Хапп: {e}"