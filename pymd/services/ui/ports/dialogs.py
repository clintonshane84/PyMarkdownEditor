from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from PyQt6.QtWidgets import QGroupBox, QFormLayout, QLabel, QLineEdit, QComboBox, QSpinBox


@runtime_checkable
class IFileDialogService(Protocol):
    """
    Abstract UI port for file dialogs. Keeps the rest of the app decoupled from Qt.
    """

    def get_open_file(
            self,
            parent: Any | None,
            caption: str,
            start_dir: str | None,
            filter_str: str,
    ) -> Path | None:
        """Return a selected file path or None if cancelled."""
        ...

    def get_save_file(
            self,
            parent: Any | None,
            caption: str,
            start_path: str | None,
            filter_str: str,
    ) -> Path | None:
        """Return a selected destination path or None if cancelled."""
        ...
