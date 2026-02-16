from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from secrets import token_hex

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from pymd.services.focus.session_writer import SessionWriter
from pymd.services.focus.timer_settings import TimerSettings


class FocusStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass(frozen=True)
class StartSessionRequest:
    title: str
    tag: str
    folder: Path
    focus_minutes: int
    break_minutes: int
    existing_note_path: Path | None = None


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
    stopped_at: datetime | None = None
    remaining_seconds: int = 0
    pause_started_at: datetime | None = None
    break_spans_seconds: list[int] = field(default_factory=list)

    @property
    def preset_label(self) -> str:
        return f"{self.focus_minutes}/{self.break_minutes}"

    @property
    def expected_focus_seconds(self) -> int:
        return max(0, self.focus_minutes * 60)

    @property
    def actual_focus_seconds(self) -> int:
        return max(0, self.expected_focus_seconds - self.remaining_seconds)

    def break_total_seconds(self) -> int:
        return sum(self.break_spans_seconds)

    def status(self) -> FocusStatus:
        if self.paused:
            return FocusStatus.PAUSED
        if self.stopped:
            return FocusStatus.COMPLETED
        return FocusStatus.ACTIVE


class FocusSessionService(QObject):
    """Run focus countdown, autosave cycle, and log session lifecycle."""

    tick = pyqtSignal(int, int)  # remaining_seconds, total_seconds
    state_changed = pyqtSignal(bool, bool)  # is_active, is_paused
    session_started = pyqtSignal(object)  # FocusSessionState
    session_stopped = pyqtSignal(object)  # dict log entry
    stop_failed = pyqtSignal(str)

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

    @property
    def is_active(self) -> bool:
        return self._state is not None and not self._state.stopped

    @property
    def is_paused(self) -> bool:
        return self.is_active and bool(self._state and self._state.paused)

    def start_session(self, req: StartSessionRequest) -> FocusSessionState:
        if self.is_active:
            raise RuntimeError("Cannot start a new focus session while another is active.")

        start_at = datetime.now().astimezone()
        session_id = self._build_session_id(start_at)
        if req.existing_note_path is not None:
            note_path = req.existing_note_path
        else:
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
        now = datetime.now().astimezone()
        self._state.paused = True
        self._state.pause_started_at = now
        self._state.interruptions += 1
        self._countdown.stop()
        self._autosave.stop()
        self._autosave_now()
        self.state_changed.emit(True, True)
        return True

    def resume(self) -> bool:
        if not self._state or self._state.stopped or not self._state.paused:
            return False
        now = datetime.now().astimezone()
        if self._state.pause_started_at is not None:
            span = max(0, int((now - self._state.pause_started_at).total_seconds()))
            self._state.break_spans_seconds.append(span)
            self._state.pause_started_at = None
        self._state.paused = False
        self._start_timers()
        self.state_changed.emit(True, False)
        return True

    def stop(self) -> dict[str, object] | None:
        if not self._state or self._state.stopped:
            return None
        self._countdown.stop()
        self._autosave.stop()
        self.safe_autosave()

        now = datetime.now().astimezone()
        state = self._state
        state.stopped = True
        state.stopped_at = now
        if state.pause_started_at is not None:
            span = max(0, int((now - state.pause_started_at).total_seconds()))
            state.break_spans_seconds.append(span)
            state.pause_started_at = None

        configured_focus_minutes = state.focus_minutes
        entry: dict[str, object] = {
            "id": state.session_id,
            "start": state.start_at.isoformat(timespec="seconds"),
            "end": now.isoformat(timespec="seconds"),
            "duration_min": configured_focus_minutes,
            "preset": state.preset_label,
            "tag": state.tag,
            "title": state.title or "Focus Session",
            "note_path": str(state.note_path),
            "interruptions": state.interruptions,
            "actual_focus_min": round(state.actual_focus_seconds / 60, 2),
            "expected_focus_min": round(state.expected_focus_seconds / 60, 2),
            "break_total_sec": state.break_total_seconds(),
        }
        try:
            self._writer.append_log(log_entry=entry, at_time=now)
        except Exception as exc:
            self.stop_failed.emit(f"Failed to append session log: {exc}")
        self.state_changed.emit(False, False)
        self.session_stopped.emit(entry)
        return entry

    def _start_timers(self) -> None:
        self._countdown.start()
        interval_ms = self._timer_settings.get_autosave_interval_min() * 60_000
        self._autosave.start(interval_ms)

    def _autosave_now(self) -> None:
        self._save_active_note()

    def safe_autosave(self) -> bool:
        if not self.is_active:
            return False
        try:
            self._autosave_now()
            return True
        except Exception as exc:
            self.stop_failed.emit(f"Failed to auto-save active session note: {exc}")
            return False

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

    def _build_session_id(self, when: datetime) -> str:
        return f"{when.strftime('%Y%m%dT%H%M%S%f')}-{token_hex(2)}"
