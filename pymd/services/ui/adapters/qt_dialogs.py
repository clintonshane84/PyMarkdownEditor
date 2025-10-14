from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QFileDialog

from pymd.services.ui.ports.dialogs import IFileDialogService


class QtFileDialogService(IFileDialogService):
    """Qt-backed implementation of file dialogs."""

    def get_open_file(
        self,
        parent: Any | None,
        caption: str,
        start_dir: str | None,
        filter_str: str,
    ) -> Path | None:
        path_str, _ = QFileDialog.getOpenFileName(
            parent,
            caption,
            start_dir or "",
            filter_str,
        )
        return Path(path_str) if path_str else None

    def get_save_file(
        self,
        parent: Any | None,
        caption: str,
        start_path: str | None,
        filter_str: str,
    ) -> Path | None:
        path_str, _ = QFileDialog.getSaveFileName(
            parent,
            caption,
            start_path or "",
            filter_str,
        )
        return Path(path_str) if path_str else None
