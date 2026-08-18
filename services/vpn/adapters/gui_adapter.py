import os
import time
import subprocess
import ctypes
from ctypes import wintypes
import psutil
import cv2
import numpy as np
from PIL import ImageGrab
import pyautogui

pyautogui.FAILSAFE = False


class GuiAdapter:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.templates_dir = os.path.join(self.base_dir, "templates")
        self._cached_sota_target = None

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

    def _find_best_match(self, template_paths: list, hwnd: int = 0, threshold: float = 0.65):
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
                    bbox = (rect.left, rect.top, rect.right, rect.bottom)
                    screen = np.array(ImageGrab.grab(bbox=bbox))
                    offset_x, offset_y = rect.left, rect.top
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

    def click_app_toggle(self, app_name: str, hwnd: int = 0, retries: int = 10, delay: float = 0.15) -> bool:
        template_paths = self._collect_template_paths(app_name)
        if not template_paths:
            return False

        for _ in range(retries):
            coords = self._find_best_match(template_paths, hwnd=hwnd)
            if coords:
                pyautogui.click(coords[0], coords[1])
                time.sleep(0.2)
                return True
            time.sleep(delay)

        return False

    def handle_conflict_popups(self, app_name: str, hwnd: int = 0):
        conflict_templates = self._collect_template_paths(app_name, subfolder="conflicts")
        if conflict_templates:
            coords = self._find_best_match(conflict_templates, hwnd=hwnd, threshold=0.70)
            if coords:
                pyautogui.click(coords[0], coords[1])
                time.sleep(0.3)

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

    def _find_sota_target(self) -> str:
        if self._cached_sota_target and os.path.exists(self._cached_sota_target):
            return self._cached_sota_target

        for proc in psutil.process_iter(['name', 'exe']):
            try:
                name = (proc.info.get('name') or '').lower()
                if "sota" in name and not name.startswith("sotad") and "daemon" not in name:
                    exe_path = proc.info.get('exe')
                    if exe_path and os.path.exists(exe_path):
                        self._cached_sota_target = exe_path
                        return exe_path
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("PROGRAMFILES", "")
        prog_files_x86 = os.environ.get("PROGRAMFILES(X86)", "")
        user_profile = os.environ.get("USERPROFILE", "")
        public_profile = os.environ.get("PUBLIC", r"C:\Users\Public")
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")

        shortcut_dirs = [
            os.path.join(user_profile, "Desktop"),
            os.path.join(public_profile, "Desktop"),
            os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(program_data, "Microsoft", "Windows", "Start Menu", "Programs")
        ]

        for s_dir in shortcut_dirs:
            if os.path.exists(s_dir):
                for root, _, files in os.walk(s_dir):
                    for f in files:
                        if "sota" in f.lower() and f.lower().endswith(".lnk"):
                            target = os.path.join(root, f)
                            self._cached_sota_target = target
                            return target

        search_roots = [appdata, localappdata, prog_files, prog_files_x86]
        for s_root in search_roots:
            if not s_root or not os.path.exists(s_root):
                continue
            try:
                for entry in os.listdir(s_root):
                    entry_low = entry.lower()
                    if "sota" in entry_low or "interhive" in entry_low:
                        full_entry_dir = os.path.join(s_root, entry)
                        if os.path.isdir(full_entry_dir):
                            for root, _, files in os.walk(full_entry_dir):
                                for f in files:
                                    fl = f.lower()
                                    if fl.endswith(".exe") and not fl.startswith("sotad") and "daemon" not in fl and "sing-box" not in fl and "xray" not in fl and "tun2socks" not in fl and "unins" not in fl:
                                        target = os.path.join(root, f)
                                        self._cached_sota_target = target
                                        return target
            except Exception:
                continue

        return ""

    def _launch_target(self, target_path: str):
        if target_path.lower().endswith(".lnk"):
            os.startfile(target_path)
        else:
            subprocess.Popen(f'"{target_path}"', shell=True)

    def toggle_sota(self):
        try:
            hwnd = self._get_window_hwnd(["Sota Connect", "Sota"], ["sota connect.exe", "sotaconnect.exe", "sota.exe", "sotaconnectclient.exe"])

            if not hwnd:
                target_path = self._find_sota_target()
                if target_path:
                    self._launch_target(target_path)
                    for _ in range(12):
                        time.sleep(0.2)
                        hwnd = self._get_window_hwnd(["Sota Connect", "Sota"], ["sota connect.exe", "sotaconnect.exe", "sota.exe", "sotaconnectclient.exe"])
                        if hwnd:
                            break
                else:
                    return "Не удалось найти путь к приложению Сота"

            self._show_and_focus(hwnd)

            if self.click_app_toggle("sota_connect", hwnd=hwnd):
                self._minimize(hwnd)
                return "Сделала!"

            return "Открыла Соту"
        except Exception as e:
            return f"Не удалось запустить Соту: {e}"

    def toggle_happ(self):
        try:
            hwnd = self._get_window_hwnd(["Happ"], ["happ.exe"])

            if not hwnd:
                subprocess.Popen(["cmd", "/c", "start", "happ:"], shell=True)
                for _ in range(12):
                    time.sleep(0.2)
                    hwnd = self._get_window_hwnd(["Happ"], ["happ.exe"])
                    if hwnd:
                        break

            self._show_and_focus(hwnd)
            self.handle_conflict_popups("happ", hwnd=hwnd)

            if self.click_app_toggle("happ", hwnd=hwnd):
                self._minimize(hwnd)
                return "Сделала!"

            return "Открыла Хапп"
        except Exception as e:
            return f"Не удалось запустить Хапп: {e}"