from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings

from pymd.services.focus.timer_settings import TimerSettings
from pymd.services.ui.focus_dialogs import TimerSettingsDialog


def test_timer_settings_dialog_profile_change_auto_previews(qapp, tmp_path: Path, monkeypatch):
    qs = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    dlg = TimerSettingsDialog(timer_settings=TimerSettings(qs))
    calls = {"n": 0}
    monkeypatch.setattr(
        dlg, "_preview_selected_sound", lambda: calls.__setitem__("n", calls["n"] + 1)
    )
    dlg.sound_profile_combo.setCurrentText("Chime")
    qapp.processEvents()
    assert calls["n"] >= 1


def test_timer_settings_dialog_custom_browse_can_preview(qapp, tmp_path: Path, monkeypatch):
    sound_path = tmp_path / "alarm.wav"
    sound_path.write_bytes(b"RIFFxxxxWAVE")
    qs = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    dlg = TimerSettingsDialog(timer_settings=TimerSettings(qs))
    dlg.sound_profile_combo.setCurrentText("Custom file")
    calls = {"n": 0}
    monkeypatch.setattr(
        dlg, "_preview_selected_sound", lambda: calls.__setitem__("n", calls["n"] + 1)
    )
    monkeypatch.setattr(
        "pymd.services.ui.focus_dialogs.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(sound_path), "Audio (*.wav)"),
    )
    dlg._browse_sound()
    qapp.processEvents()
    assert dlg.custom_sound_edit.text() == str(sound_path)
    assert calls["n"] >= 1
