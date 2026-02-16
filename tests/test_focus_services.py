from __future__ import annotations

from pathlib import Path

import pytest
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
    settings.set_sound_profile("chime")
    settings.set_custom_sound_path(tmp_path / "alarm.wav")
    settings.set_default_folder(tmp_path)

    assert settings.get_autosave_interval_min() == 3
    assert settings.get_sound_enabled() is True
    assert settings.get_sound_profile() == "chime"
    assert settings.get_custom_sound_path() == tmp_path / "alarm.wav"
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
    assert service.state is not None
    assert len(service.state.break_spans_seconds) == 1
    log = service.stop()
    assert log is not None
    assert log["preset"] == "50/10"
    assert log["interruptions"] == 1
    assert "actual_focus_min" in log
    assert "expected_focus_min" in log
    assert "break_total_sec" in log

    log_path = tmp_path / ".focusforge" / "logs"
    files = list(log_path.glob("*.jsonl"))
    assert files, "Expected at least one JSONL log file."
    log_content = files[0].read_text(encoding="utf-8")
    assert '"tag": "PL-900"' in log_content


def test_focus_session_service_rejects_start_when_active(tmp_path: Path):
    qs = QSettings(str(tmp_path / "session.ini"), QSettings.Format.IniFormat)
    timer_settings = TimerSettings(qs)
    service = FocusSessionService(
        writer=SessionWriter(FileService()),
        timer_settings=timer_settings,
        save_active_note=lambda: True,
    )
    req = StartSessionRequest(
        title="S1",
        tag="A",
        folder=tmp_path,
        focus_minutes=25,
        break_minutes=5,
    )
    service.start_session(req)
    with pytest.raises(RuntimeError):
        service.start_session(req)


def test_focus_session_service_stop_emits_failure_but_does_not_raise(tmp_path: Path):
    qs = QSettings(str(tmp_path / "session.ini"), QSettings.Format.IniFormat)
    timer_settings = TimerSettings(qs)
    writer = SessionWriter(FileService())
    service = FocusSessionService(
        writer=writer,
        timer_settings=timer_settings,
        save_active_note=lambda: True,
    )
    req = StartSessionRequest(
        title="S1",
        tag="A",
        folder=tmp_path,
        focus_minutes=25,
        break_minutes=5,
    )
    service.start_session(req)
    writer.append_log = lambda **kwargs: (_ for _ in ()).throw(OSError("log failure"))  # type: ignore[method-assign]
    failures: list[str] = []
    service.stop_failed.connect(failures.append)
    entry = service.stop()
    assert entry is not None
    assert failures
    assert "log failure" in failures[0]


def test_focus_session_service_note_name_collision_gets_suffix(tmp_path: Path):
    qs = QSettings(str(tmp_path / "session.ini"), QSettings.Format.IniFormat)
    timer_settings = TimerSettings(qs)
    service = FocusSessionService(
        writer=SessionWriter(FileService()),
        timer_settings=timer_settings,
        save_active_note=lambda: True,
    )
    service._build_session_id = lambda _when: "20260216T141500000000"  # type: ignore[method-assign]
    req = StartSessionRequest(
        title="Power Apps recap",
        tag="PL-900",
        folder=tmp_path,
        focus_minutes=50,
        break_minutes=10,
    )
    first = service.start_session(req)
    service.stop()
    second = service.start_session(req)
    assert first.note_path != second.note_path
    assert second.note_path.name.endswith("-1.md")


def test_focus_session_service_chaos_monkey_failures_are_contained(tmp_path: Path):
    qs = QSettings(str(tmp_path / "session.ini"), QSettings.Format.IniFormat)
    timer_settings = TimerSettings(qs)
    service = FocusSessionService(
        writer=SessionWriter(FileService()),
        timer_settings=timer_settings,
        save_active_note=lambda: True,
    )
    req = StartSessionRequest(
        title="Chaos",
        tag="X",
        folder=tmp_path,
        focus_minutes=25,
        break_minutes=5,
    )
    state = service.start_session(req)
    assert state.note_path.exists()

    counters = {"save": 0, "log": 0}

    def flaky_save() -> bool:
        counters["save"] += 1
        if counters["save"] % 2 == 0:
            raise OSError("autosave chaos")
        return True

    def flaky_log(**kwargs):
        counters["log"] += 1
        if counters["log"] % 2 == 1:
            raise OSError("log chaos")
        return tmp_path / "ok.jsonl"

    service._save_active_note = flaky_save  # type: ignore[assignment]
    service._writer.append_log = flaky_log  # type: ignore[method-assign]

    failures: list[str] = []
    service.stop_failed.connect(failures.append)

    assert service.safe_autosave() is True
    assert service.safe_autosave() is False
    assert service.pause() is True
    assert service.resume() is True
    assert service.stop() is not None
    assert failures
    assert any("autosave chaos" in msg or "log chaos" in msg for msg in failures)
