from __future__ import annotations

import math
import platform
import shutil
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from pymd.services.focus.timer_settings import TimerSettings


@dataclass(frozen=True)
class SessionDialogResult:
    title: str
    tag: str
    folder: Path
    focus_minutes: int
    break_minutes: int
    use_current_note: bool = False


class StartSessionDialog(QDialog):
    """Collect metadata and preset details before a focus session starts."""

    def __init__(
        self,
        *,
        timer_settings: TimerSettings,
        current_note_path: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start Focus Session")
        self._timer_settings = timer_settings
        self._current_note_path = current_note_path

        self.title_edit = QLineEdit(self)
        self.tag_edit = QLineEdit(self)
        self.preset_combo = QComboBox(self)
        self.preset_combo.addItems(["25 / 5", "50 / 10", "Custom"])
        self.preset_combo.setCurrentIndex(1)

        self.focus_spin = QSpinBox(self)
        self.focus_spin.setRange(1, 240)
        self.focus_spin.setValue(50)

        self.break_spin = QSpinBox(self)
        self.break_spin.setRange(0, 120)
        self.break_spin.setValue(10)

        self.folder_edit = QLineEdit(self)
        self.folder_btn = QPushButton("Browse…", self)
        self.folder_btn.clicked.connect(self._browse_folder)
        self.use_current_note_cb = QCheckBox("Use current note (continue in this file)", self)
        self.use_current_note_cb.setChecked(current_note_path is not None)
        self.use_current_note_cb.setEnabled(current_note_path is not None)

        default_folder = timer_settings.get_default_folder() or Path.home()
        self.folder_edit.setText(str(default_folder))

        form = QFormLayout()
        form.addRow("Title (optional)", self.title_edit)
        form.addRow("Tag (optional)", self.tag_edit)
        form.addRow("Duration preset", self.preset_combo)
        form.addRow("Focus minutes", self.focus_spin)
        form.addRow("Break minutes", self.break_spin)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(self.folder_btn)
        form.addRow("Where to store this session?", folder_row)
        form.addRow("", self.use_current_note_cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self.use_current_note_cb.toggled.connect(self._on_use_current_note_toggled)
        self._on_preset_changed(self.preset_combo.currentText())
        self._on_use_current_note_toggled(self.use_current_note_cb.isChecked())

    def get_result(self) -> SessionDialogResult | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        folder = Path(self.folder_edit.text().strip()).expanduser()
        return SessionDialogResult(
            title=self.title_edit.text().strip(),
            tag=self.tag_edit.text().strip(),
            folder=folder,
            focus_minutes=int(self.focus_spin.value()),
            break_minutes=int(self.break_spin.value()),
            use_current_note=self.use_current_note_cb.isChecked(),
        )

    def _browse_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Session Folder",
            self.folder_edit.text().strip() or str(Path.home()),
        )
        if selected:
            self.folder_edit.setText(selected)

    def _on_preset_changed(self, value: str) -> None:
        if value == "25 / 5":
            self.focus_spin.setValue(25)
            self.break_spin.setValue(5)
            self.focus_spin.setEnabled(False)
            self.break_spin.setEnabled(False)
        elif value == "50 / 10":
            self.focus_spin.setValue(50)
            self.break_spin.setValue(10)
            self.focus_spin.setEnabled(False)
            self.break_spin.setEnabled(False)
        else:
            self.focus_spin.setEnabled(True)
            self.break_spin.setEnabled(True)

    def _on_accept(self) -> None:
        if self.use_current_note_cb.isChecked() and self._current_note_path is not None:
            self.accept()
            return
        folder_text = self.folder_edit.text().strip()
        if not folder_text:
            QMessageBox.warning(self, "Missing folder", "Choose a folder to store this session.")
            return
        folder = Path(folder_text).expanduser()
        if not folder.exists():
            QMessageBox.warning(self, "Invalid folder", "The selected folder does not exist.")
            return
        self.accept()

    def _on_use_current_note_toggled(self, checked: bool) -> None:
        self.folder_edit.setEnabled(not checked)
        self.folder_btn.setEnabled(not checked)


class TimerSettingsDialog(QDialog):
    """Edit timer-level settings persisted via QSettings."""

    def __init__(self, *, timer_settings: TimerSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Timer Settings")
        self._settings = timer_settings

        self.autosave_spin = QSpinBox(self)
        self.autosave_spin.setRange(1, 60)
        self.autosave_spin.setValue(timer_settings.get_autosave_interval_min())

        self.sound_cb = QCheckBox("Enable finish sound", self)
        self.sound_cb.setChecked(timer_settings.get_sound_enabled())
        self.sound_profile_combo = QComboBox(self)
        self._sound_profiles = {
            "Beep": "beep",
            "Chime": "chime",
            "Bell": "bell",
            "Ping": "ping",
            "Custom file": "custom",
        }
        self.sound_profile_combo.addItems(list(self._sound_profiles.keys()))

        current_profile = timer_settings.get_sound_profile()
        for idx, label in enumerate(self._sound_profiles):
            if self._sound_profiles[label] == current_profile:
                self.sound_profile_combo.setCurrentIndex(idx)
                break
        self.auto_preview_cb = QCheckBox("Auto-preview sound", self)
        self.auto_preview_cb.setChecked(True)
        self.preview_sound_btn = QPushButton("Preview", self)
        self.preview_sound_btn.clicked.connect(self._preview_selected_sound)

        self.default_folder_edit = QLineEdit(self)
        self.default_folder_btn = QPushButton("Browse…", self)
        self.default_folder_btn.clicked.connect(self._browse_folder)
        default_folder = timer_settings.get_default_folder()
        self.default_folder_edit.setText(str(default_folder) if default_folder else "")

        self.custom_sound_edit = QLineEdit(self)
        self.custom_sound_btn = QPushButton("Browse sound…", self)
        self.custom_sound_btn.clicked.connect(self._browse_sound)
        custom_sound = timer_settings.get_custom_sound_path()
        self.custom_sound_edit.setText(str(custom_sound) if custom_sound else "")
        self._preview_effects: dict[str, object] = {}
        self._preview_media_player = None
        self._preview_audio_output = None

        form = QFormLayout()
        form.addRow("Auto-save interval (minutes)", self.autosave_spin)
        form.addRow("", self.sound_cb)
        form.addRow("Alarm sound", self.sound_profile_combo)
        preview_row = QHBoxLayout()
        preview_row.addWidget(self.auto_preview_cb)
        preview_row.addStretch(1)
        preview_row.addWidget(self.preview_sound_btn)
        form.addRow("", preview_row)
        custom_sound_row = QHBoxLayout()
        custom_sound_row.addWidget(self.custom_sound_edit, 1)
        custom_sound_row.addWidget(self.custom_sound_btn)
        form.addRow("Custom sound file", custom_sound_row)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.default_folder_edit, 1)
        folder_row.addWidget(self.default_folder_btn)
        form.addRow("Default session folder", folder_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)
        self.sound_profile_combo.currentTextChanged.connect(self._on_sound_profile_changed)
        self._on_sound_profile_changed(self.sound_profile_combo.currentText())

    def _browse_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Default Session Folder",
            self.default_folder_edit.text().strip() or str(Path.home()),
        )
        if selected:
            self.default_folder_edit.setText(selected)

    def _browse_sound(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select sound file",
            self.custom_sound_edit.text().strip() or str(Path.home()),
            "Audio (*.wav *.mp3 *.ogg);;All files (*)",
        )
        if selected:
            self.custom_sound_edit.setText(selected)
            if self.auto_preview_cb.isChecked():
                self._preview_selected_sound()

    def _on_accept(self) -> None:
        folder_raw = self.default_folder_edit.text().strip()
        folder_path: Path | None = None
        profile = self._sound_profiles[self.sound_profile_combo.currentText()]
        custom_sound_path: Path | None = None
        if folder_raw:
            folder_path = Path(folder_raw).expanduser()
            if not folder_path.exists():
                QMessageBox.warning(
                    self, "Invalid folder", "The selected default folder does not exist."
                )
                return
        if profile == "custom":
            raw_sound = self.custom_sound_edit.text().strip()
            if not raw_sound:
                QMessageBox.warning(
                    self, "Missing sound", "Choose a custom sound file or select another sound."
                )
                return
            custom_sound_path = Path(raw_sound).expanduser()
            if not custom_sound_path.exists():
                QMessageBox.warning(
                    self, "Invalid sound", "The selected sound file does not exist."
                )
                return
        self._settings.set_autosave_interval_min(self.autosave_spin.value())
        self._settings.set_sound_enabled(self.sound_cb.isChecked())
        self._settings.set_sound_profile(profile)
        self._settings.set_custom_sound_path(custom_sound_path)
        self._settings.set_default_folder(folder_path)
        self.accept()

    def _on_sound_profile_changed(self, label: str) -> None:
        is_custom = self._sound_profiles.get(label) == "custom"
        self.custom_sound_edit.setEnabled(is_custom)
        self.custom_sound_btn.setEnabled(is_custom)
        if self.auto_preview_cb.isChecked():
            self._preview_selected_sound()

    def _preview_selected_sound(self) -> None:
        profile = self._sound_profiles[self.sound_profile_combo.currentText()]
        if profile == "beep":
            QApplication.beep()
            return
        path = self._resolve_preview_sound_path(profile)
        if path is None:
            QApplication.beep()
            return
        if not self._play_sound_file(path):
            QApplication.beep()

    def _resolve_preview_sound_path(self, profile: str) -> Path | None:
        if profile == "custom":
            raw = self.custom_sound_edit.text().strip()
            if not raw:
                return None
            custom = Path(raw).expanduser()
            return custom if custom.exists() else None
        return self._ensure_preview_tone(profile)

    def _play_sound_file(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix != ".wav":
            return self._play_media_sound_file(path)
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtMultimedia import QSoundEffect  # type: ignore
        except Exception:
            return self._play_media_sound_file(path)
        try:
            key = str(path)
            effect = self._preview_effects.get(key)
            if effect is None:
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(0.90)
                self._preview_effects[key] = effect
            effect.play()
            return True
        except Exception:
            return self._play_media_sound_file(path)

    def _play_media_sound_file(self, path: Path) -> bool:
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer  # type: ignore
        except Exception:
            return self._play_system_sound_file(path)
        try:
            if self._preview_media_player is None or self._preview_audio_output is None:
                audio = QAudioOutput(self)
                audio.setVolume(0.95)
                player = QMediaPlayer(self)
                player.setAudioOutput(audio)
                self._preview_audio_output = audio
                self._preview_media_player = player
            self._preview_media_player.setSource(QUrl.fromLocalFile(str(path)))
            self._preview_media_player.play()
            return True
        except Exception:
            return self._play_system_sound_file(path)

    def _play_system_sound_file(self, path: Path) -> bool:
        system = platform.system()
        if system == "Darwin":
            afplay = shutil.which("afplay")
            if afplay:
                try:
                    subprocess.Popen(
                        [afplay, str(path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True
                except Exception:
                    return False
        return False

    def _ensure_preview_tone(self, profile: str) -> Path:
        out = Path(tempfile.gettempdir()) / f"pymd_timer_preview_{profile}.wav"
        if out.exists():
            return out
        sample_rate = 44_100
        amplitude = 16000
        tones = self._tone_pattern(profile)
        with wave.open(str(out), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            for freq, dur in tones:
                if freq <= 0:
                    silence_frames = int(sample_rate * dur)
                    wav_file.writeframesraw(b"\x00\x00" * silence_frames)
                    continue
                frames = int(sample_rate * dur)
                for i in range(frames):
                    angle = 2.0 * math.pi * freq * (i / sample_rate)
                    sample = int(amplitude * math.sin(angle))
                    wav_file.writeframesraw(struct.pack("<h", sample))
        return out

    def _tone_pattern(self, profile: str) -> list[tuple[float, float]]:
        if profile == "chime":
            return [(659.0, 0.15), (0.0, 0.05), (880.0, 0.20)]
        if profile == "bell":
            return [(523.0, 0.25), (392.0, 0.20)]
        if profile == "ping":
            return [(1046.0, 0.12)]
        return [(880.0, 0.20)]
