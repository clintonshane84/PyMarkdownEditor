from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import QSaveFile, QIODevice

from pymd.domain.interfaces import IFileService


class FileService(IFileService):
    """Atomic reads/writes for text files."""

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_text_atomic(self, path: Path, text: str) -> None:
        sf = QSaveFile(str(path))
        if not sf.open(QIODevice.OpenModeFlag.WriteOnly):
            raise IOError(f"Cannot open for write: {path}")
        sf.write(text.encode("utf-8"))
        if not sf.commit():
            raise IOError(f"Commit failed for: {path}")
