from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pymd.plugins.catalog import PluginCatalogItem, default_catalog
from pymd.plugins.pip_installer import PipResult, QtPipInstaller
from pymd.plugins.state import IPluginStateStore
from pymd.services.ui.plugins.pip_progress_dialog import PipProgressDialog


class _PipSignals(Protocol):
    """
    Narrow protocol for QtPipInstaller-like objects.
    Matches your exact signal shapes:
      - output: pyqtSignal(str)
      - finished: pyqtSignal(object)  # PipResult
    """

    output: object
    finished: object


class _InstalledRowLike(Protocol):
    """
    Minimal row shape required by PluginsDialog.

    NOTE:
      - package is optional because PluginManager may return PluginInfo-like objects
        without a package attribute (built-ins, older versions, etc.)
    """

    plugin_id: str
    name: str
    version: str
    description: str

    # optional
    package: str  # may not exist at runtime


@dataclass(frozen=True)
class InstalledPluginRow:
    """
    Installed plugin model for the UI.

    `package` is optional but recommended:
    - Allows uninstall for plugins not present in the catalog.
    """

    plugin_id: str
    name: str
    version: str
    description: str
    package: str = ""


class PluginsDialog(QDialog):
    """
    Plugin Manager UI:
      - Installed plugins: enable/disable + uninstall (if package known)
      - Catalog plugins: install
      - Reload button to re-discover & activate enabled plugins
    """

    COL_ENABLED = 0
    COL_PLUGIN_ID = 1
    COL_NAME = 2
    COL_VERSION = 3
    COL_PACKAGE = 4
    COL_SOURCE = 5
    COL_ACTION = 6

    ROLE_PLUGIN_ID = int(Qt.ItemDataRole.UserRole)
    ROLE_SOURCE = int(Qt.ItemDataRole.UserRole) + 1
    ROLE_PACKAGE = int(Qt.ItemDataRole.UserRole) + 2

    SOURCE_INSTALLED = "Installed"
    SOURCE_CATALOG = "Catalog"

    def __init__(
        self,
        *,
        parent=None,
        state: IPluginStateStore,
        pip: QtPipInstaller,
            get_installed: Callable[[], Sequence[_InstalledRowLike]],
        reload_plugins: Callable[[], None],
        catalog: Sequence[PluginCatalogItem] | None = None,
        auto_reload_on_toggle: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plugins")
        self.resize(980, 540)

        self._state = state
        self._pip = pip
        self._get_installed = get_installed
        self._reload_plugins = reload_plugins
        self._catalog = list(catalog or default_catalog())
        self._auto_reload_on_toggle = auto_reload_on_toggle

        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._safe_reload_plugins)

        layout = QVBoxLayout(self)

        # ---- top bar ----
        top = QHBoxLayout()
        top.addWidget(QLabel("Search:", self))

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Filter by name, plugin id, or package…")
        self._search.textChanged.connect(self._apply_filter)
        top.addWidget(self._search, 1)

        self.btn_refresh = QPushButton("Refresh", self)
        self.btn_reload = QPushButton("Reload plugins", self)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_reload)

        layout.addLayout(top)

        # ---- table ----
        self.table = QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Enabled", "Plugin ID", "Name", "Version", "Package", "Source", "Action"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_ENABLED, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_PLUGIN_ID, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_VERSION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_PACKAGE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_SOURCE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_ACTION, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table, 1)

        # ---- bottom bar ----
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_close = QPushButton("Close", self)
        bottom.addWidget(self.btn_close)
        layout.addLayout(bottom)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_reload.clicked.connect(self._on_reload_clicked)
        self.btn_close.clicked.connect(self.close)

        self.table.itemChanged.connect(self._on_item_changed)

        self.refresh()

    # ----------------------------- table -----------------------------

    def refresh(self) -> None:
        installed_rows = list(self._get_installed())
        installed_by_id = {p.plugin_id: p for p in installed_rows}

        # (pid, name, ver, desc, pkg, source, action)
        rows: list[tuple[str, str, str, str, str, str, str]] = []

        # installed plugins first
        for p in installed_rows:
            # FIX: package is optional on row-like objects
            pkg = str(getattr(p, "package", "") or "").strip()

            # uninstall allowed if we can map to a package (either from row or catalog)
            can_uninstall = bool(pkg) or bool(self._pip_package_for(p.plugin_id))
            action = "Uninstall" if can_uninstall else "—"
            rows.append((p.plugin_id, p.name, p.version, p.description, pkg, self.SOURCE_INSTALLED, action))

        # catalog plugins not installed
        for c in self._catalog:
            if c.plugin_id not in installed_by_id:
                rows.append(
                    (c.plugin_id, c.name, "", c.description, c.pip_package, self.SOURCE_CATALOG, "Install")
                )

        rows.sort(key=lambda x: (x[5] != self.SOURCE_INSTALLED, x[1].lower(), x[0].lower()))

        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(rows))

            for r, (pid, name, ver, desc, pkg, source, action) in enumerate(rows):
                is_installed = source == self.SOURCE_INSTALLED
                enabled = self._state.get_enabled(pid, default=False)

                enabled_item = QTableWidgetItem()
                enabled_item.setData(self.ROLE_PLUGIN_ID, pid)
                enabled_item.setData(self.ROLE_SOURCE, source)
                enabled_item.setData(self.ROLE_PACKAGE, pkg)

                if is_installed:
                    enabled_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    enabled_item.setCheckState(
                        Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
                    )
                else:
                    enabled_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    enabled_item.setCheckState(Qt.CheckState.Unchecked)

                self.table.setItem(r, self.COL_ENABLED, enabled_item)
                self.table.setItem(r, self.COL_PLUGIN_ID, QTableWidgetItem(pid))

                name_item = QTableWidgetItem(name)
                if desc:
                    name_item.setToolTip(desc)
                self.table.setItem(r, self.COL_NAME, name_item)

                self.table.setItem(r, self.COL_VERSION, QTableWidgetItem(ver))
                self.table.setItem(r, self.COL_PACKAGE, QTableWidgetItem(pkg))
                self.table.setItem(r, self.COL_SOURCE, QTableWidgetItem(source))

                btn = QPushButton(action, self)
                btn.setEnabled(action in ("Install", "Uninstall"))
                btn.clicked.connect(lambda _=False, xpid=pid, xaction=action: self._on_action(xpid, xaction))
                self.table.setCellWidget(r, self.COL_ACTION, btn)
        finally:
            self.table.blockSignals(False)

        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self._search.text().strip().lower()
        for r in range(self.table.rowCount()):
            pid = (
                self.table.item(r, self.COL_PLUGIN_ID).text() if self.table.item(r, self.COL_PLUGIN_ID) else "").lower()
            name = (self.table.item(r, self.COL_NAME).text() if self.table.item(r, self.COL_NAME) else "").lower()
            pkg = (self.table.item(r, self.COL_PACKAGE).text() if self.table.item(r, self.COL_PACKAGE) else "").lower()

            show = not needle or (needle in pid or needle in name or needle in pkg)
            self.table.setRowHidden(r, not show)

    # -------------------------- enable / disable -------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != self.COL_ENABLED:
            return

        source = item.data(self.ROLE_SOURCE)
        if source != self.SOURCE_INSTALLED:
            return

        pid = item.data(self.ROLE_PLUGIN_ID)
        if not pid:
            return

        enabled = item.checkState() == Qt.CheckState.Checked
        self._state.set_enabled(str(pid), enabled)

        if self._auto_reload_on_toggle:
            self._reload_timer.start(200)

    # ----------------------------- reload -----------------------------

    def _safe_reload_plugins(self) -> None:
        try:
            self._reload_plugins()
        except Exception:
            pass

    def _on_reload_clicked(self) -> None:
        self._safe_reload_plugins()
        QMessageBox.information(self, "Plugins", "Plugins reloaded.")
        self.refresh()

    # ----------------------------- actions -----------------------------

    def _on_action(self, plugin_id: str, action: str) -> None:
        pkg = self._pip_package_for(plugin_id) or self._installed_package_for(plugin_id)
        if not pkg:
            QMessageBox.critical(self, "Plugins", f"Cannot determine pip package for {plugin_id}.")
            return

        if action == "Install":
            self._run_pip(f"Installing {pkg}…", lambda: self._pip.install(pkg))
            return

        if action == "Uninstall":
            resp = QMessageBox.question(self, "Uninstall", f"Uninstall {pkg}?")
            if resp != QMessageBox.StandardButton.Yes:
                return
            self._run_pip(f"Uninstalling {pkg}…", lambda: self._pip.uninstall(pkg))
            return

    def _pip_package_for(self, plugin_id: str) -> str | None:
        for c in self._catalog:
            if c.plugin_id == plugin_id:
                pkg = (c.pip_package or "").strip()
                return pkg or None
        return None

    def _installed_package_for(self, plugin_id: str) -> str | None:
        for p in self._get_installed():
            if p.plugin_id == plugin_id:
                pkg = str(getattr(p, "package", "") or "").strip()
                return pkg or None
        return None

    # ----------------------------- pip runner -----------------------------

    def _run_pip(self, title: str, start: Callable[[], None]) -> None:
        dlg = PipProgressDialog(title, parent=self)

        pip_obj = self._pip
        has_signals = (
            isinstance(pip_obj, QObject)
            and hasattr(pip_obj, "output")
            and hasattr(pip_obj, "finished")
        )
        if not has_signals:
            QMessageBox.critical(
                self,
                "Plugins",
                "This build does not support streaming pip output (QtPipInstaller not wired).",
            )
            return

        pip_qt = cast(_PipSignals, pip_obj)

        def on_output(text: str) -> None:
            dlg.append(text)

        def on_finished(result_obj: object) -> None:
            try:
                result = cast(PipResult, result_obj)
                if result.ok:
                    dlg.set_done(True, "Done.")
                else:
                    dlg.set_done(False, f"Failed (exit code {result.exit_code}). See log.")
                self.refresh()
                self._safe_reload_plugins()
            finally:
                try:
                    pip_qt.output.disconnect(on_output)  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    pip_qt.finished.disconnect(on_finished)  # type: ignore[attr-defined]
                except Exception:
                    pass

        pip_qt.output.connect(on_output)  # type: ignore[attr-defined]
        pip_qt.finished.connect(on_finished)  # type: ignore[attr-defined]

        if hasattr(pip_obj, "cancel"):
            dlg.btn_cancel.clicked.connect(lambda: pip_obj.cancel())  # type: ignore[misc]
        else:
            dlg.btn_cancel.setEnabled(False)

        dlg.btn_close.clicked.connect(dlg.accept)

        start()
        dlg.exec()
