import os
import json
import random
import threading
import subprocess
import time
import winreg
import re
import spotipy
from spotipy.oauth2 import SpotifyOAuth


class SpotifyManager:
    def __init__(self):
        self.sp = None
        self.scope = (
            "user-read-playback-state "
            "user-modify-playback-state "
            "user-read-currently-playing "
            "user-library-read "
            "user-library-modify "
            "playlist-read-private"
        )
        self.device_id = None

    def _load_credentials(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(base_dir, "personal_data", "configs", "config.json")
        template_path = os.path.join(base_dir, "personal_data", "configs", "config.template.json")
        target_path = config_path if os.path.exists(config_path) else template_path

        client_id, client_secret = "", ""
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    api_keys = cfg.get("api_keys", {})
                    client_id = api_keys.get("spotify_client_id", "")
                    client_secret = api_keys.get("spotify_client_secret", "")
            except Exception:
                pass
        return client_id, client_secret

    def _init_client(self):
        if self.sp is not None:
            return True

        client_id, client_secret = self._load_credentials()
        if not client_id or not client_secret:
            return False

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_dir = os.path.join(base_dir, "personal_data", "configs")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, ".spotify_cache")

        try:
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri="http://127.0.0.1:8888/callback",
                scope=self.scope,
                cache_path=cache_path,
                open_browser=True
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            return True
        except Exception as e:
            print(f"[Spotify Init Error]: {e}")
            return False

    def _is_spotify_installed(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"spotify\shell\open\command")
            val, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
            if val:
                match = re.search(r'"([^"]+Spotify\.exe)"', val, re.IGNORECASE)
                if match and os.path.exists(match.group(1)):
                    return match.group(1)
                exe_cand = val.split('"')[1] if '"' in val else val.split()[0]
                if os.path.exists(exe_cand):
                    return exe_cand
        except Exception:
            pass

        user_roaming = os.environ.get("APPDATA", "")
        user_local = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")

        candidate_paths = [
            os.path.join(user_roaming, "Spotify", "Spotify.exe"),
            os.path.join(user_local, "Microsoft", "WindowsApps", "Spotify.exe"),
            os.path.join(prog_files, "Spotify", "Spotify.exe"),
            os.path.join(prog_files_x86, "Spotify", "Spotify.exe")
        ]

        windows_apps = os.path.join(user_local, "Microsoft", "WindowsApps")
        if os.path.exists(windows_apps):
            try:
                for entry in os.listdir(windows_apps):
                    if "spotify" in entry.lower():
                        full_p = os.path.join(windows_apps, entry, "Spotify.exe")
                        if os.path.exists(full_p):
                            candidate_paths.append(full_p)
            except Exception:
                pass

        for p in candidate_paths:
            if p and os.path.exists(p):
                return p

        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Spotify.exe")
            val, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
            if val and os.path.exists(val):
                return val
        except Exception:
            pass

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Spotify.exe")
            val, _ = winreg.QueryValueEx(key, "")
            winreg.CloseKey(key)
            if val and os.path.exists(val):
                return val
        except Exception:
            pass

        return None

    def _launch_app(self):
        installed_path = self._is_spotify_installed()
        if not installed_path:
            return False

        try:
            subprocess.Popen([installed_path])
            return True
        except Exception:
            pass

        try:
            subprocess.Popen(["cmd", "/c", "start", "spotify:"], shell=True)
            return True
        except Exception:
            return False

    def _ensure_active_device_async(self):
        try:
            devices = self.sp.devices().get("devices", [])
            if devices:
                active_dev = next((d for d in devices if d.get("is_active")), devices[0])
                self.device_id = active_dev["id"]
                return True

            if not self._launch_app():
                return False

            for _ in range(8):
                time.sleep(1.0)
                devices = self.sp.devices().get("devices", [])
                if devices:
                    active_dev = next((d for d in devices if d.get("is_active")), devices[0])
                    self.device_id = active_dev["id"]
                    return True

        except Exception as e:
            print(f"[Spotify Device Async Error]: {e}")
        return False

    def play_query(self, query):
        if not self._load_credentials()[0]:
            return "Укажи client_id и client_secret для Spotify в настройках"

        if not self._is_spotify_installed():
            return "Прости, я не нашла на твоем ПК Спотик! Установи приложение, и я сразу включу музыку."

        display_name = query.title()

        def _async_play():
            try:
                if not self._init_client():
                    return

                if not self._ensure_active_device_async():
                    return

                res = self.sp.search(q=query, limit=1, type="track,artist")
                tracks = res.get("tracks", {}).get("items", [])

                if tracks:
                    track_uri = tracks[0]["uri"]
                    self.sp.start_playback(device_id=self.device_id, uris=[track_uri])
                else:
                    artists = res.get("artists", {}).get("items", [])
                    if artists:
                        artist_uri = artists[0]["uri"]
                        self.sp.start_playback(device_id=self.device_id, context_uri=artist_uri)
            except Exception as e:
                print(f"[Spotify Play Error]: {e}")

        threading.Thread(target=_async_play, daemon=True).start()
        return f"Включаю {display_name} в Spotify"

    def play_my_wave(self):
        if not self._load_credentials()[0]:
            return "Укажи client_id и client_secret для Spotify в настройках"

        if not self._is_spotify_installed():
            return "Прости, я не нашла на твоем ПК Спотик! Установи приложение, и я сразу включу музыку."

        def _async_wave():
            try:
                if not self._init_client():
                    return

                if not self._ensure_active_device_async():
                    return

                saved = self.sp.current_user_saved_tracks(limit=20)
                items = saved.get("items", [])

                if items:
                    track_uris = [item["track"]["uri"] for item in items]
                    random.shuffle(track_uris)

                    seed_ids = [item["track"]["id"] for item in random.sample(items, min(3, len(items)))]
                    recs = self.sp.recommendations(seed_tracks=seed_ids, limit=20)
                    rec_uris = [t["uri"] for t in recs.get("tracks", [])]

                    all_uris = track_uris[:5] + rec_uris
                    self.sp.start_playback(device_id=self.device_id, uris=all_uris)
            except Exception as e:
                print(f"[Spotify Wave Error]: {e}")

        threading.Thread(target=_async_wave, daemon=True).start()
        return True

    def toggle_pause(self):
        def _async_toggle():
            if not self._init_client():
                return
            try:
                state = self.sp.current_playback()
                if state and state.get("is_playing"):
                    self.sp.pause_playback()
                else:
                    self.sp.start_playback()
            except Exception as e:
                print(f"[Spotify Pause Error]: {e}")
        threading.Thread(target=_async_toggle, daemon=True).start()

    def stop(self):
        def _async_stop():
            if not self._init_client():
                return
            try:
                self.sp.pause_playback()
            except Exception:
                pass
        threading.Thread(target=_async_stop, daemon=True).start()
        return "Выключаю музыку"

    def next_track(self):
        threading.Thread(target=lambda: self._init_client() and self.sp.next_track(), daemon=True).start()

    def prev_track(self):
        threading.Thread(target=lambda: self._init_client() and self.sp.previous_track(), daemon=True).start()

    def like_current(self):
        def _async_like():
            if not self._init_client():
                return
            try:
                current = self.sp.current_user_playing_track()
                if current and current.get("item"):
                    track_id = current["item"]["id"]
                    self.sp.current_user_saved_tracks_add([track_id])
            except Exception as e:
                print(f"[Spotify Like Error]: {e}")
        threading.Thread(target=_async_like, daemon=True).start()

    def unlike_current(self):
        def _async_unlike():
            if not self._init_client():
                return
            try:
                current = self.sp.current_user_playing_track()
                if current and current.get("item"):
                    track_id = current["item"]["id"]
                    self.sp.current_user_saved_tracks_delete([track_id])
            except Exception as e:
                print(f"[Spotify Unlike Error]: {e}")
        threading.Thread(target=_async_unlike, daemon=True).start()

    def set_shuffle(self, state: bool = True):
        threading.Thread(target=lambda: self._init_client() and self.sp.shuffle(state), daemon=True).start()

    def set_volume(self, volume_percent: int):
        vol = max(0, min(100, volume_percent))
        threading.Thread(target=lambda: self._init_client() and self.sp.volume(vol), daemon=True).start()