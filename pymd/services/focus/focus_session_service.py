from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from pymd.services.focus.session_writer import SessionWriter
from pymd.services.focus.timer_settings import TimerSettings


@dataclass(frozen=True)
class StartSessionRequest:
    title: str
    tag: str
    folder: Path
    focus_minutes: int
    break_minutes: int


@dataclass
class FocusSessionState:
    session_id: str
    title: str
    tag: str
    note_path: Path
    start_at: datetime
    focus_minutes: int
    break_minutes: int
    interruptions: int = 0
    paused: bool = False
    stopped: bool = False
    remaining_seconds: int = 0

    @property
    def preset_label(self) -> str:
        return f"{self.focus_minutes}/{self.break_minutes}"


class FocusSessionService(QObject):
    """Run focus countdown, autosave cycle, and log session lifecycle."""

    tick = pyqtSignal(int, int)  # remaining_seconds, total_seconds
    state_changed = pyqtSignal(bool, bool)  # is_active, is_paused
    session_started = pyqtSignal(object)  # FocusSessionState
    session_stopped = pyqtSignal(object)  # dict log entry

    def __init__(
        self,
        *,
        writer: SessionWriter,
        timer_settings: TimerSettings,
        save_active_note: Callable[[], bool],
        on_finish_sound: Callable[[], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._writer = writer
        self._timer_settings = timer_settings
        self._save_active_note = save_active_note
        self._on_finish_sound = on_finish_sound
        self._state: FocusSessionState | None = None

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._on_tick)

        self._autosave = QTimer(self)
        self._autosave.timeout.connect(self._autosave_now)

    @property
    def state(self) -> FocusSessionState | None:
        return self._state

    def start_session(self, req: StartSessionRequest) -> FocusSessionState:
        if self._state and not self._state.stopped:
            self.stop()

        start_at = datetime.now().astimezone()
        session_id = start_at.strftime("%Y%m%dT%H%M%S")
        note_path = self._writer.create_note(
            folder=req.folder,
            session_id=session_id,
            start_at=start_at,
            focus_minutes=req.focus_minutes,
            break_minutes=req.break_minutes,
            title=req.title,
            tag=req.tag,
            interruptions=0,
        )
        self._state = FocusSessionState(
            session_id=session_id,
            title=req.title.strip(),
            tag=req.tag.strip(),
            note_path=note_path,
            start_at=start_at,
            focus_minutes=req.focus_minutes,
            break_minutes=req.break_minutes,
            interruptions=0,
            paused=False,
            stopped=False,
            remaining_seconds=max(1, req.focus_minutes * 60),
        )
        self._start_timers()
        self.tick.emit(self._state.remaining_seconds, self._state.focus_minutes * 60)
        self.state_changed.emit(True, False)
        self.session_started.emit(self._state)
        return self._state

    def pause(self) -> bool:
        if not self._state or self._state.stopped or self._state.paused:
            return False
        self._state.paused = True
        self._state.interruptions += 1
        self._countdown.stop()
        self._autosave.stop()
        self._autosave_now()
        self.state_changed.emit(True, True)
        return True

    def resume(self) -> bool:
        if not self._state or self._state.stopped or not self._state.paused:
            return False
        self._state.paused = False
        self._start_timers()
        self.state_changed.emit(True, False)
        return True

    def stop(self) -> dict[str, object] | None:
        if not self._state or self._state.stopped:
            return None
        self._countdown.stop()
        self._autosave.stop()
        self._autosave_now()

        now = datetime.now().astimezone()
        state = self._state
        state.stopped = True

        planned_duration = state.focus_minutes
        entry: dict[str, object] = {
            "id": state.session_id,
            "start": state.start_at.isoformat(timespec="seconds"),
            "end": now.isoformat(timespec="seconds"),
            "duration_min": planned_duration,
            "preset": state.preset_label,
            "tag": state.tag,
            "title": state.title or "Focus Session",
            "note_path": str(state.note_path),
            "interruptions": state.interruptions,
        }
        self._writer.append_log(log_entry=entry, at_time=now)
        self.state_changed.emit(False, False)
        self.session_stopped.emit(entry)
        return entry

    def _start_timers(self) -> None:
        self._countdown.start()
        interval_ms = self._timer_settings.get_autosave_interval_min() * 60_000
        self._autosave.start(interval_ms)

    def _autosave_now(self) -> None:
        self._save_active_note()

    def _on_tick(self) -> None:
        if not self._state or self._state.paused or self._state.stopped:
            return
        self._state.remaining_seconds = max(0, self._state.remaining_seconds - 1)
        total = self._state.focus_minutes * 60
        self.tick.emit(self._state.remaining_seconds, total)
        if self._state.remaining_seconds == 0:
            if self._timer_settings.get_sound_enabled() and self._on_finish_sound:
                self._on_finish_sound()
            self.stop()
