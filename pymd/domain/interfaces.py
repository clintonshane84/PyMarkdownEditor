from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol


class IMarkdownRenderer(Protocol):
    """Convert Markdown text to full HTML string (including CSS)."""

    def to_html(self, markdown_text: str) -> str: ...


class IFileService(Protocol):
    """Read/write text files. Writes should be atomic when possible."""

    def read_text(self, path: Path) -> str: ...

    def write_text_atomic(self, path: Path, text: str) -> None: ...


class ISettingsService(Protocol):
    """Persist and retrieve lightweight UI state."""

    # Window/layout state
    def get_geometry(self) -> bytes | None: ...

    def set_geometry(self, blob: bytes) -> None: ...

    def get_splitter(self) -> bytes | None: ...

    def set_splitter(self, blob: bytes) -> None: ...

    # Recent files
    def get_recent(self) -> list[str]: ...

    def set_recent(self, recent: Iterable[str]) -> None: ...

    # Generic key/value (used by plugins state store etc.)
    def get_raw(self, key: str, default: str | None = None) -> str | None: ...

    def set_raw(self, key: str, value: str) -> None: ...


class IExporter(ABC):
    """Export strategy interface. Implementations export HTML to a given format/path."""

    name: str  # e.g. "html", "pdf"
    label: str  # e.g. "Export HTML…"

    @abstractmethod
    def export(self, html: str, out_path: Path) -> None:
        """Perform export. 'html' contains a full HTML document string."""
        raise NotImplementedError


class IMarkdownView:  # implemented by MainWindow
    def set_editor_text(self, text: str) -> None: ...

    def editor_text(self) -> str: ...

    def set_preview_html(self, html: str) -> None: ...

    def set_title(self, title: str) -> None: ...

    def set_status(self, msg: str, ms: int = 3000) -> None: ...

    def toggle_preview(self, on: bool) -> None: ...

    def toggle_wrap(self, on: bool) -> None: ...

    # events exposed as Qt signals or simple call-ins
    # e.g., on_text_changed, on_new, on_open, on_save, etc.


class IExporterRegistry(ABC):
    @abstractmethod
    def all(self) -> list[IExporter]: ...

    @abstractmethod
    def get(self, name: str) -> IExporter: ...

    @abstractmethod
    def register(self, e: IExporter) -> None: ...


class IFileDialogService:
    def open_file(self, caption: str, filters: str) -> Path | None: ...

    def save_file(self, caption: str, start: str, filters: str) -> Path | None: ...


class IMessageService:
    def error(self, title: str, text: str) -> None: ...

    def question_yes_no(self, title: str, text: str) -> bool: ...


class IConfigService(Protocol):
    """Read-only application configuration (backed by INI/TOML/etc.)."""

    def get(self, section: str, key: str, default: str | None = None) -> str | None:
        """Return a string value or default (no side-effects)."""

    def get_int(self, section: str, key: str, default: int | None = None) -> int | None: ...

    def get_bool(self, section: str, key: str, default: bool | None = None) -> bool | None: ...

    def as_dict(self) -> Mapping[str, Mapping[str, str]]:
        """A copy of the current config map (for diagnostics/About dialog)."""

    # Convenience for very common keys
    def app_version(self) -> str: ...


class IAppConfig(IConfigService, Protocol):
    """
    Full config contract for the application.
    Must include all public IniConfigService methods + app version.
    """

    def get_version(self) -> str: ...
