import os
import threading
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from comtypes import CoInitialize, CoUninitialize


class VolumeDucker:
    def __init__(self):
        self.saved_volumes = {}
        self._lock = threading.Lock()
        self._duck_count = 0

    def _duck_async(self, factor=0.05):
        try:
            CoInitialize()
            sessions = AudioUtilities.GetAllSessions()
            current_pid = os.getpid()

            for session in sessions:
                process = session.Process
                if process:
                    name = process.name().lower()
                    if process.pid == current_pid or "astra" in name or "python" in name or "pycharm" in name:
                        continue

                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                    current_vol = volume.GetMasterVolume()

                    if process.pid not in self.saved_volumes:
                        self.saved_volumes[process.pid] = current_vol

                    orig_vol = self.saved_volumes[process.pid]
                    volume.SetMasterVolume(orig_vol * factor, None)
        except Exception as e:
            print(f"[Volume Ducker Error]: {e}", flush=True)
        finally:
            try:
                CoUninitialize()
            except Exception:
                pass

    def duck(self, factor=0.05):
        with self._lock:
            self._duck_count += 1
            if self._duck_count == 1:
                threading.Thread(target=self._duck_async, args=(factor,), daemon=True).start()
            try:
                from core.system.actions import ym_manager
                ym_manager.duck(factor)
            except Exception:
                pass

    def _restore_async(self):
        if not self.saved_volumes:
            return

        try:
            CoInitialize()
            sessions = AudioUtilities.GetAllSessions()

            for session in sessions:
                process = session.Process
                if process and process.pid in self.saved_volumes:
                    try:
                        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                        saved_vol = self.saved_volumes[process.pid]
                        volume.SetMasterVolume(saved_vol, None)
                    except Exception:
                        pass

            self.saved_volumes.clear()
        except Exception as e:
            print(f"[Volume Ducker Error]: {e}", flush=True)
        finally:
            try:
                CoUninitialize()
            except Exception:
                pass

    def restore(self):
        with self._lock:
            if self._duck_count > 0:
                self._duck_count -= 1
            if self._duck_count == 0:
                threading.Thread(target=self._restore_async, daemon=True).start()
                try:
                    from core.system.actions import ym_manager
                    ym_manager.unduck()
                except Exception:
                    pass

    def force_restore(self):
        with self._lock:
            self._duck_count = 0
            threading.Thread(target=self._restore_async, daemon=True).start()
            try:
                from core.system.actions import ym_manager
                ym_manager.unduck()
            except Exception:
                pass


volume_ducker = VolumeDucker()