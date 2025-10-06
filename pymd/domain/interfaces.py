from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, Iterable


class IMarkdownRenderer(Protocol):
    """Convert Markdown text to full HTML string (including CSS)."""

    def to_html(self, markdown_text: str) -> str: ...


class IFileService(Protocol):
    """Read/write text files. Writes should be atomic when possible."""

    def read_text(self, path: Path) -> str: ...
    def write_text_atomic(self, path: Path, text: str) -> None: ...


class ISettingsService(Protocol):
    """Persist and retrieve lightweight UI state."""

    def get_geometry(self) -> bytes | None: ...
    def set_geometry(self, blob: bytes) -> None: ...
    def get_splitter(self) -> bytes | None: ...
    def set_splitter(self, blob: bytes) -> None: ...
    def get_recent(self) -> list[str]: ...
    def set_recent(self, recent: Iterable[str]) -> None: ...


class IExporter(ABC):
    """Export strategy interface. Implementations export HTML to a given format/path."""

    name: str  # e.g. "html", "pdf"
    label: str  # e.g. "Export HTML…"

    @abstractmethod
    def export(self, html: str, out_path: Path) -> None:
        """Perform export. 'html' contains a full HTML document string."""
        raise NotImplementedError
