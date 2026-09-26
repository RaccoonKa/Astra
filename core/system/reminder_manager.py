import os
import json
import uuid
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QSoundEffect
from core.utils.config import get_user_data_path, get_resource_path
from core.system.volume_ducker import volume_ducker


class ReminderManager(QObject):
    alarm_fired = pyqtSignal(dict)
    timer_fired = pyqtSignal(dict)
    reminder_fired = pyqtSignal(dict)
    missed_reminders_signal = pyqtSignal(list)
    state_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = get_user_data_path("configs", "reminders.json")
        self.tasks = []
        self.is_ringing = False
        self.active_task = None
        self.failsafe_counter = 0
        self.pending_reminder = None

        self._is_ducked_by_sound = False
        self.sound_effect = QSoundEffect(self)
        self.sound_effect.playingChanged.connect(self._on_sound_playing_changed)
        self.sound_effect.statusChanged.connect(self._on_sound_status_changed)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        self._load_and_filter_tasks()

    def _load_and_filter_tasks(self):
        if not os.path.exists(self.file_path):
            self.tasks = []
            return

        now = datetime.now()
        raw_list = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
        except Exception:
            raw_list = []

        valid_tasks = []
        missed_reminders = []

        for item in raw_list:
            try:
                fire_at = datetime.fromisoformat(item["fire_at"])
                if fire_at > now:
                    valid_tasks.append(item)
                else:
                    if item.get("type") == "reminder":
                        if now - fire_at <= timedelta(hours=2):
                            missed_reminders.append(item.get("text", "Без темы"))
            except Exception:
                pass

        self.tasks = valid_tasks
        self._save_tasks()

        if missed_reminders:
            QTimer.singleShot(2500, lambda: self.missed_reminders_signal.emit(missed_reminders))

    def _save_tasks(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ReminderManager Save Error]: {e}", flush=True)

    def _on_sound_status_changed(self):
        if self.sound_effect.status() == QSoundEffect.Status.Error:
            if self.pending_reminder:
                task = self.pending_reminder
                self.pending_reminder = None
                self.reminder_fired.emit(task)

    def _on_sound_playing_changed(self):
        if self.sound_effect.isPlaying():
            if not self._is_ducked_by_sound:
                self._is_ducked_by_sound = True
                volume_ducker.duck(factor=0.05)
        else:
            if self._is_ducked_by_sound:
                self._is_ducked_by_sound = False
                volume_ducker.restore()

            if self.is_ringing and self.active_task and self.active_task.get("type") == "timer":
                self.is_ringing = False
                self.active_task = None
                self.state_changed.emit()

            if self.pending_reminder:
                task = self.pending_reminder
                self.pending_reminder = None
                self.reminder_fired.emit(task)

    def add_timer(self, seconds: int, label: str = "") -> dict:
        from core.system.time_parser import TimeParser
        fire_at = datetime.now() + timedelta(seconds=seconds)
        dur_label = label or f"Таймер на {TimeParser.format_duration(seconds)}"
        task = {
            "id": f"tmr_{uuid.uuid4().hex[:8]}",
            "type": "timer",
            "fire_at": fire_at.isoformat(),
            "text": dur_label,
            "duration": seconds
        }
        self.tasks.append(task)
        self._save_tasks()
        self.state_changed.emit()
        return task

    def add_alarm(self, target_dt: datetime, label: str = "") -> dict:
        task = {
            "id": f"alm_{uuid.uuid4().hex[:8]}",
            "type": "alarm",
            "fire_at": target_dt.isoformat(),
            "text": label or "Будильник",
            "snooze_count": 0
        }
        self.tasks.append(task)
        self._save_tasks()
        self.state_changed.emit()
        return task

    def add_reminder(self, target_dt: datetime, text: str) -> dict:
        task = {
            "id": f"rem_{uuid.uuid4().hex[:8]}",
            "type": "reminder",
            "fire_at": target_dt.isoformat(),
            "text": text
        }
        self.tasks.append(task)
        self._save_tasks()
        self.state_changed.emit()
        return task

    def _play_sound(self, sound_type: str, loop_count: int = 1) -> bool:
        path = None

        if sound_type == "alarm":
            from core.utils.config import load_config
            cfg = load_config()
            alarm_mode = cfg.get("alarm_sound", "alarm_1")
            custom_path = cfg.get("custom_alarm_path", "")

            if alarm_mode == "custom" and custom_path and os.path.exists(custom_path):
                path = custom_path
            else:
                track_name = f"{alarm_mode}.wav" if alarm_mode in ["alarm_1", "alarm_2", "alarm_3"] else "alarm_1.wav"
                path = get_resource_path("assets", "sounds", track_name)
                if not os.path.exists(path):
                    path = get_resource_path("assets", "sounds", "alarm.wav")
        else:
            filename = f"{sound_type}.wav"
            path = get_resource_path("assets", "sounds", filename)

        if not path or not os.path.exists(path):
            fallback = get_resource_path("assets", "sounds", "notification.wav")
            path = fallback if os.path.exists(fallback) else None

        if path:
            try:
                self.sound_effect.stop()
                self.sound_effect.setSource(QUrl.fromLocalFile(path))
                self.sound_effect.setLoopCount(loop_count)
                self.sound_effect.setVolume(1.0)
                self.sound_effect.play()
                return True
            except Exception as e:
                print(f"[Sound Error]: {e}", flush=True)
                return False

        return False

    def cancel_timers(self) -> int:
        count_before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("type") != "timer"]
        removed = count_before - len(self.tasks)
        if removed > 0:
            self._save_tasks()
            self.state_changed.emit()
        return removed

    def cancel_alarms(self) -> int:
        count_before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("type") != "alarm"]
        removed = count_before - len(self.tasks)
        if removed > 0:
            self._save_tasks()
            self.state_changed.emit()
        return removed

    def cancel_reminders(self, search_text: str = "") -> int:
        count_before = len(self.tasks)
        if search_text:
            self.tasks = [
                t for t in self.tasks
                if not (t.get("type") == "reminder" and search_text.lower() in t.get("text", "").lower())
            ]
        else:
            self.tasks = [t for t in self.tasks if t.get("type") != "reminder"]
        removed = count_before - len(self.tasks)
        if removed > 0:
            self._save_tasks()
            self.state_changed.emit()
        return removed

    def stop_ringing(self) -> bool:
        if not self.is_ringing and not self.pending_reminder:
            return False

        self.sound_effect.stop()
        self.is_ringing = False
        self.active_task = None
        self.pending_reminder = None
        self.failsafe_counter = 0

        if self._is_ducked_by_sound:
            self._is_ducked_by_sound = False
            volume_ducker.restore()

        self.state_changed.emit()
        return True

    def snooze(self, minutes: int = 5) -> bool:
        if not self.is_ringing or not self.active_task:
            return False

        self.sound_effect.stop()
        self.is_ringing = False

        if self._is_ducked_by_sound:
            self._is_ducked_by_sound = False
            volume_ducker.restore()

        new_fire_at = datetime.now() + timedelta(minutes=minutes)
        self.active_task["fire_at"] = new_fire_at.isoformat()
        self.active_task["snooze_count"] = self.active_task.get("snooze_count", 0) + 1

        self.tasks.append(self.active_task)
        self._save_tasks()

        self.active_task = None
        self.failsafe_counter = 0
        self.state_changed.emit()
        return True

    def _tick(self):
        if self.is_ringing:
            self.failsafe_counter += 1
            if self.failsafe_counter >= 120:
                self.stop_ringing()
            return

        now = datetime.now()
        ready_tasks = []
        remaining_tasks = []

        for task in self.tasks:
            try:
                fire_at = datetime.fromisoformat(task["fire_at"])
                if fire_at <= now:
                    ready_tasks.append(task)
                else:
                    remaining_tasks.append(task)
            except Exception:
                pass

        if ready_tasks:
            self.tasks = remaining_tasks
            self._save_tasks()

            target_task = ready_tasks[0]
            self.active_task = target_task
            t_type = target_task.get("type", "reminder")

            if t_type == "alarm":
                self.is_ringing = True
                self.failsafe_counter = 0
                self._play_sound("alarm", loop_count=QSoundEffect.Loop.Infinite)
                self.alarm_fired.emit(target_task)
            elif t_type == "timer":
                self.is_ringing = True
                self.failsafe_counter = 0
                self._play_sound("timer", loop_count=4)
                self.timer_fired.emit(target_task)
            else:
                self.pending_reminder = target_task
                started = self._play_sound("reminder", loop_count=1)
                if not started:
                    self.pending_reminder = None
                    self.reminder_fired.emit(target_task)

            self.state_changed.emit()