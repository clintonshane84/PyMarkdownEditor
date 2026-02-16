from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import (
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


class StartSessionDialog(QDialog):
    """Collect metadata and preset details before a focus session starts."""

    def __init__(self, *, timer_settings: TimerSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start Focus Session")
        self._timer_settings = timer_settings

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

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self._on_preset_changed(self.preset_combo.currentText())

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
        folder_text = self.folder_edit.text().strip()
        if not folder_text:
            QMessageBox.warning(self, "Missing folder", "Choose a folder to store this session.")
            return
        folder = Path(folder_text).expanduser()
        if not folder.exists():
            QMessageBox.warning(self, "Invalid folder", "The selected folder does not exist.")
            return
        self.accept()


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

        self.default_folder_edit = QLineEdit(self)
        self.default_folder_btn = QPushButton("Browse…", self)
        self.default_folder_btn.clicked.connect(self._browse_folder)
        default_folder = timer_settings.get_default_folder()
        self.default_folder_edit.setText(str(default_folder) if default_folder else "")

        form = QFormLayout()
        form.addRow("Auto-save interval (minutes)", self.autosave_spin)
        form.addRow("", self.sound_cb)

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

    def _browse_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Default Session Folder",
            self.default_folder_edit.text().strip() or str(Path.home()),
        )
        if selected:
            self.default_folder_edit.setText(selected)

    def _on_accept(self) -> None:
        folder_raw = self.default_folder_edit.text().strip()
        folder_path: Path | None = None
        if folder_raw:
            folder_path = Path(folder_raw).expanduser()
            if not folder_path.exists():
                QMessageBox.warning(
                    self, "Invalid folder", "The selected default folder does not exist."
                )
                return
        self._settings.set_autosave_interval_min(self.autosave_spin.value())
        self._settings.set_sound_enabled(self.sound_cb.isChecked())
        self._settings.set_default_folder(folder_path)
        self.accept()
