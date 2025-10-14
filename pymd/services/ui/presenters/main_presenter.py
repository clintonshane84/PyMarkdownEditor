from __future__ import annotations

from typing import Protocol, runtime_checkable

from pymd.domain.interfaces import IFileService, IMarkdownRenderer, ISettingsService
from pymd.services.exporters import ExporterRegistryInst
from pymd.services.ui.ports.dialogs import IFileDialogService
from pymd.services.ui.ports.messages import IMessageService


@runtime_checkable
class IMainView(Protocol):
    """Very small surface for a passive view (implemented by the Qt MainWindow)."""

    # editor/preview
    def get_editor_text(self) -> str: ...
    def set_editor_text(self, text: str) -> None: ...
    def set_preview_html(self, html: str) -> None: ...

    # window chrome
    def set_modified(self, modified: bool) -> None: ...
    def is_modified(self) -> bool: ...
    def set_title(self, title: str) -> None: ...

    # recents
    def set_recents(self, items: list[str]) -> None: ...

    # status + errors
    def show_status(self, text: str, msec: int = 3000) -> None: ...
    def show_error(self, title: str, text: str) -> None: ...


class MainPresenter:
    """
    Optional coordinator for the main window; safe to introduce gradually.
    You can migrate open/save/export logic here over time.
    """

    def __init__(
        self,
        view: IMainView,
        renderer: IMarkdownRenderer,
        files: IFileService,
        settings: ISettingsService,
        messages: IMessageService,
        dialogs: IFileDialogService,
    ) -> None:
        self.view = view
        self.renderer = renderer
        self.files = files
        self.settings = settings
        self.messages = messages
        self.dialogs = dialogs

    # Example small methods; expand as you migrate responsibilities.
    def render_preview(self) -> None:
        html = self.renderer.to_html(self.view.get_editor_text())
        self.view.set_preview_html(html)

    def export_via_dialog(self) -> None:
        # example: pick first exporter for brevity; wire proper menu later
        exporters = list(ExporterRegistryInst.all())
        if not exporters:
            self.messages.error(None, "Export", "No exporters registered.")
            return
        exporter = exporters[0]
        default = f"document.{exporter.name}"
        out = self.dialogs.get_save_file(
            None, exporter.label, default, f"{exporter.name.upper()} (*.{exporter.name})"
        )
        if not out:
            return
        try:
            exporter.export(self.renderer.to_html(self.view.get_editor_text()), out)
            self.view.show_status(f"Exported {exporter.name.upper()}: {out}", 3000)
        except Exception as e:  # pragma: no cover (UI error path)
            self.messages.error(None, "Export Error", f"Failed to export:\n{e}")
