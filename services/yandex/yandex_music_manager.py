import os
import re
import random
import threading
import time
import hashlib
import xml.etree.ElementTree as ET
import requests
import webbrowser
from core.utils.config import load_config

vlc_paths = [
    r"C:\Program Files\VideoLAN\VLC",
    r"C:\Program Files (x86)\VideoLAN\VLC"
]
for p in vlc_paths:
    if os.path.exists(p):
        try:
            os.add_dll_directory(p)
        except Exception:
            pass
        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

try:
    import vlc
    HAS_VLC = True
except Exception:
    vlc = None
    HAS_VLC = False

from yandex_music import Client


class YandexMusicManager:
    def __init__(self):
        self.client = None
        if HAS_VLC:
            self.vlc_instance = vlc.Instance('--no-video', '--quiet')
            self.player = self.vlc_instance.media_player_new()
        else:
            self.vlc_instance = None
            self.player = None
        self.queue = []
        self.history = []
        self.current_track = None
        self.is_radio = False
        self.watcher_thread = None
        self.stop_watcher = False
        self.is_transitioning = False

    def _extract_pure_token(self, raw_token):
        if not raw_token:
            return ""
        if "access_token=" in raw_token:
            match = re.search(r'access_token=([^&]+)', raw_token)
            if match:
                return match.group(1)
        return raw_token.strip()

    def _init_client(self):
        if not HAS_VLC:
            return False

        if self.client is not None:
            return True

        cfg = load_config()
        raw_token = cfg.get("api_keys", {}).get("yandex_music_token", "")
        token = self._extract_pure_token(raw_token)

        if not token:
            return False

        try:
            self.client = Client(token).init()
            return True
        except Exception as e:
            print(f"[YandexMusic Init Error]: {e}")
            return False

    def _get_direct_stream_url(self, track):
        try:
            if not hasattr(track, 'get_download_info') and hasattr(track, 'fetch_track'):
                track = track.fetch_track()

            info_list = track.get_download_info()
            if not info_list:
                return None
            info_sorted = sorted(info_list, key=lambda x: getattr(x, 'bitrate_in_kbps', 0), reverse=True)
            best_info = info_sorted[0]

            if hasattr(best_info, 'get_direct_url') and callable(getattr(best_info, 'get_direct_url')):
                try:
                    return best_info.get_direct_url()
                except Exception:
                    pass

            if hasattr(best_info, 'direct_url') and best_info.direct_url:
                return best_info.direct_url

            download_url = getattr(best_info, 'download_info_url', None)
            if download_url:
                resp = requests.get(download_url, timeout=5)
                if resp.status_code == 200:
                    xml_root = ET.fromstring(resp.text)
                    host = xml_root.findtext('host')
                    path = xml_root.findtext('path')
                    ts = xml_root.findtext('ts')
                    s = xml_root.findtext('s')

                    if host and path and ts and s:
                        secret = f"XGR{path[1:]}{s}"
                        md5_hash = hashlib.md5(secret.encode('utf-8')).hexdigest()
                        return f"https://{host}/get-mp3/{md5_hash}/{ts}{path}"
        except Exception as e:
            print(f"[YandexMusic Stream Error]: {e}")
        return None

    def _play_track_object(self, track):
        if not HAS_VLC or not self.player:
            self.is_transitioning = False
            return False

        try:
            if not hasattr(track, 'get_download_info') and hasattr(track, 'fetch_track'):
                track = track.fetch_track()

            stream_url = self._get_direct_stream_url(track)
            if not stream_url:
                self.is_transitioning = False
                return False

            if self.current_track:
                self.history.append(self.current_track)

            self.current_track = track
            self.player.stop()
            media = self.vlc_instance.media_new(stream_url)
            self.player.set_media(media)
            self.player.play()
            time.sleep(0.5)
            self.is_transitioning = False
            return True
        except Exception as e:
            print(f"[YandexMusic Play Error]: {e}")
            self.is_transitioning = False
            return False

    def play_query(self, query):
        if not HAS_VLC:
            webbrowser.open("https://www.videolan.org/vlc/")
            return "Для работы Яндекс Музыки нужен плеер. Открываю официальный сайт для скачивания."

        if not self._init_client():
            return "Укажи токен Яндекс Музыки в настройках"

        self.is_transitioning = True

        def _async_play():
            try:
                search_result = self.client.search(query)
                if not search_result or not search_result.best or search_result.best.type != 'track':
                    self.is_transitioning = False
                    return

                track = search_result.best.result
                self.is_radio = False
                self.queue = []
                if self._play_track_object(track):
                    self._start_watcher()
                else:
                    self.is_transitioning = False
            except Exception as e:
                print(f"[YandexMusic Play Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_play, daemon=True).start()
        return f"Ищу {query}"

    def set_volume(self, volume: int):
        if HAS_VLC and self.player:
            self.player.audio_set_volume(max(0, min(100, volume)))

    def duck(self, level: int = 15):
        if HAS_VLC and self.player and self.player.is_playing():
            self.player.audio_set_volume(level)

    def unduck(self, level: int = 100):
        if HAS_VLC and self.player and self.player.is_playing():
            self.player.audio_set_volume(level)

    def play_my_wave(self):
        if not HAS_VLC:
            webbrowser.open("https://www.videolan.org/vlc/")
            return "Для работы +Яндекс Музыки нужен плеер. Открываю официальный сайт для скачивания."

        if not self._init_client():
            return False

        self.is_transitioning = True

        def _async_wave():
            try:
                likes = self.client.users_likes_tracks()
                if not likes:
                    self.is_transitioning = False
                    return

                track_items = list(likes.tracks) if hasattr(likes, 'tracks') else list(likes)
                if not track_items:
                    self.is_transitioning = False
                    return

                random.shuffle(track_items)
                first_track = track_items[0]
                self.queue = track_items[1:]
                self.is_radio = True

                if self._play_track_object(first_track):
                    self._start_watcher()
                else:
                    self.is_transitioning = False
            except Exception as e:
                print(f"[YandexMusic Wave Error]: {e}")
                self.is_transitioning = False

        threading.Thread(target=_async_wave, daemon=True).start()
        return True

    def toggle_pause(self):
        if not HAS_VLC or not self.player:
            return
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        if HAS_VLC and self.player:
            self.player.stop()
        self.stop_watcher = True
        self.current_track = None
        self.queue = []
        return "Музыка выключена"

    def next_track(self):
        if not HAS_VLC or self.is_transitioning:
            return

        self.is_transitioning = True

        def _async_next():
            if self.queue:
                next_tr = self.queue.pop(0)
                self._play_track_object(next_tr)
            elif self.is_radio:
                self.play_my_wave()
            else:
                self.is_transitioning = False

        threading.Thread(target=_async_next, daemon=True).start()

    def prev_track(self):
        if not HAS_VLC or self.is_transitioning:
            return

        self.is_transitioning = True

        def _async_prev():
            if self.history:
                prev_tr = self.history.pop()
                if self.current_track:
                    self.queue.insert(0, self.current_track)
                self._play_track_object(prev_tr)
            else:
                self.is_transitioning = False

        threading.Thread(target=_async_prev, daemon=True).start()

    def like_current(self):
        def _async_like():
            if not self._init_client() or not self.current_track:
                return
            try:
                self.client.users_likes_tracks_add(self.current_track.id)
            except Exception as e:
                print(f"[YandexMusic Like Error]: {e}")

        threading.Thread(target=_async_like, daemon=True).start()

    def unlike_current(self):
        def _async_unlike():
            if not self._init_client() or not self.current_track:
                return
            try:
                self.client.users_likes_tracks_remove(self.current_track.id)
            except Exception as e:
                print(f"[YandexMusic Unlike Error]: {e}")

        threading.Thread(target=_async_unlike, daemon=True).start()

    def _start_watcher(self):
        if self.watcher_thread and self.watcher_thread.is_alive():
            return
        self.stop_watcher = False
        self.watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watcher_thread.start()

    def _watch_loop(self):
        while not self.stop_watcher:
            time.sleep(0.5)
            if not HAS_VLC or not self.player:
                break
            if self.is_transitioning:
                continue
            state = self.player.get_state()
            if state == vlc.State.Ended:
                self.next_track()