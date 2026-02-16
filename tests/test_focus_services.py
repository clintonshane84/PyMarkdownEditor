from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings

from pymd.services.file_service import FileService
from pymd.services.focus import (
    FocusSessionService,
    SessionWriter,
    StartSessionRequest,
    TimerSettings,
)


def test_timer_settings_roundtrip(tmp_path: Path):
    qs = QSettings(str(tmp_path / "timer.ini"), QSettings.Format.IniFormat)
    settings = TimerSettings(qs)

    settings.set_autosave_interval_min(3)
    settings.set_sound_enabled(True)
    settings.set_default_folder(tmp_path)

    assert settings.get_autosave_interval_min() == 3
    assert settings.get_sound_enabled() is True
    assert settings.get_default_folder() == tmp_path


def test_focus_session_service_start_pause_stop(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    qs = QSettings(str(tmp_path / "session.ini"), QSettings.Format.IniFormat)
    timer_settings = TimerSettings(qs)
    files = FileService()
    writer = SessionWriter(files)

    saved = {"count": 0}

    def fake_save() -> bool:
        saved["count"] += 1
        return True

    service = FocusSessionService(
        writer=writer,
        timer_settings=timer_settings,
        save_active_note=fake_save,
    )

    req = StartSessionRequest(
        title="Power Apps recap",
        tag="PL-900",
        folder=tmp_path / "notes",
        focus_minutes=50,
        break_minutes=10,
    )
    state = service.start_session(req)
    assert state.note_path.exists()
    text = state.note_path.read_text(encoding="utf-8")
    assert "preset: 50/10" in text
    assert "tag: PL-900" in text
    assert "# Power Apps recap" in text

    assert service.pause() is True
    assert service.state is not None
    assert service.state.interruptions == 1
    assert saved["count"] >= 1

    assert service.resume() is True
    log = service.stop()
    assert log is not None
    assert log["preset"] == "50/10"
    assert log["interruptions"] == 1

    log_path = tmp_path / ".focusforge" / "logs"
    files = list(log_path.glob("*.jsonl"))
    assert files, "Expected at least one JSONL log file."
    log_content = files[0].read_text(encoding="utf-8")
    assert '"tag": "PL-900"' in log_content
