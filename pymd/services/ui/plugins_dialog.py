from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from PyQt6.QtCore import Qt, QTimer
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
from pymd.plugins.state import IPluginStateStore
from pymd.services.plugins.pip_installer import IPipInstaller, PipResult
from pymd.services.ui.plugins.pip_progress_dialog import PipProgressDialog


@dataclass(frozen=True)
class InstalledPluginRow:
    """
    Data from plugin discovery.

    NOTE:
    - `package` is strongly recommended so uninstall works for non-catalog plugins too.
    - Keep it optional for backward compatibility; if missing, uninstall will be disabled
      unless the plugin exists in catalog.
    """
    plugin_id: str
    name: str
    version: str
    description: str
    package: str = ""


class PluginsDialog(QDialog):
    """
    V1 Plugin Manager UI:
      - Installed plugins: enable/disable + uninstall (if package is known)
      - Catalog plugins: install
      - Reload button to re-discover & activate enabled plugins

    Design goals:
      - Clean separation: state store decides enabled/disabled; reload() applies it.
      - Avoid duplicate Qt signal connections during refresh() calls.
      - pip operations run async via IPipInstaller while a progress dialog shows output.
    """

    COL_ENABLED = 0
    COL_PLUGIN_ID = 1
    COL_NAME = 2
    COL_VERSION = 3
    COL_PACKAGE = 4
    COL_SOURCE = 5
    COL_ACTION = 6

    ROLE_PLUGIN_ID = int(Qt.ItemDataRole.UserRole)
    ROLE_SOURCE = int(Qt.ItemDataRole.UserRole) + 1  # "Installed" / "Catalog"
    ROLE_PACKAGE = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(
        self,
        *,
        parent=None,
        state: IPluginStateStore,
        pip: IPipInstaller,
        get_installed: Callable[[], Sequence[InstalledPluginRow]],
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

        self._reload_timer: QTimer | None = None

        layout = QVBoxLayout(self)

        # --- Top bar (search + refresh/reload) ---
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

        # --- Table ---
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

        # --- Bottom bar ---
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_close = QPushButton("Close", self)
        bottom.addWidget(self.btn_close)
        layout.addLayout(bottom)

        # events
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_reload.clicked.connect(self._on_reload)
        self.btn_close.clicked.connect(self.close)

        # connect ONCE (avoid connecting every refresh)
        self.table.itemChanged.connect(self._on_item_changed)

        self.refresh()

    # ----------------------------- Rendering -----------------------------

    def refresh(self) -> None:
        """
        Rebuild rows based on:
          - installed plugins from discovery
          - catalog plugins not installed yet
        """
        installed = {p.plugin_id: p for p in self._get_installed()}
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        # tuple = (plugin_id, name, ver, desc, package, source, action)

        # 1) installed plugins first
        for p in installed.values():
            pkg = getattr(p, "package", "") or ""
            action = "Uninstall" if pkg or self._pip_package_for(p.plugin_id) else "—"
            rows.append((p.plugin_id, p.name, p.version, p.description, pkg, "Installed", action))

        # 2) catalog plugins that are not installed
        for c in self._catalog:
            if c.plugin_id not in installed:
                rows.append((c.plugin_id, c.name, "", c.description, c.pip_package, "Catalog", "Install"))

        # stable ordering
        rows.sort(key=lambda x: (x[5] != "Installed", x[2] == "", x[1].lower(), x[0].lower()))

        # prevent recursive itemChanged while populating
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(rows))

            for r, (pid, name, ver, desc, pkg, source, action) in enumerate(rows):
                is_installed = source == "Installed"
                enabled = self._state.get_enabled(pid, default=False)

                # Enabled checkbox item
                enabled_item = QTableWidgetItem()
                enabled_item.setData(self.ROLE_PLUGIN_ID, pid)
                enabled_item.setData(self.ROLE_SOURCE, source)
                enabled_item.setData(self.ROLE_PACKAGE, pkg)

                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                if not is_installed:
                    # catalog-only: cannot enable before install
                    flags = Qt.ItemFlag.ItemIsEnabled
                enabled_item.setFlags(flags)

                if is_installed:
                    enabled_item.setCheckState(
                        Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
                    )
                else:
                    enabled_item.setCheckState(Qt.CheckState.Unchecked)

                self.table.setItem(r, self.COL_ENABLED, enabled_item)

                # Plugin ID
                pid_item = QTableWidgetItem(pid)
                self.table.setItem(r, self.COL_PLUGIN_ID, pid_item)

                # Name (tooltip with description)
                name_item = QTableWidgetItem(name)
                if desc:
                    name_item.setToolTip(desc)
                self.table.setItem(r, self.COL_NAME, name_item)

                # Version
                self.table.setItem(r, self.COL_VERSION, QTableWidgetItem(ver))

                # Package
                self.table.setItem(r, self.COL_PACKAGE, QTableWidgetItem(pkg))

                # Source
                self.table.setItem(r, self.COL_SOURCE, QTableWidgetItem(source))

                # Action button
                btn = QPushButton(action, self)
                btn.setEnabled(action in ("Install", "Uninstall"))
                btn.clicked.connect(
                    lambda _=False, xpid=pid, xaction=action: self._on_action(xpid, xaction)
                )
                self.table.setCellWidget(r, self.COL_ACTION, btn)

        finally:
            self.table.blockSignals(False)

        self._apply_filter()

    def _apply_filter(self) -> None:
        needle = self._search.text().strip().lower()
        for r in range(self.table.rowCount()):
            pid = (self.table.item(r, self.COL_PLUGIN_ID).text() if self.table.item(r, self.COL_PLUGIN_ID) else "").lower()
            name = (self.table.item(r, self.COL_NAME).text() if self.table.item(r, self.COL_NAME) else "").lower()
            pkg = (self.table.item(r, self.COL_PACKAGE).text() if self.table.item(r, self.COL_PACKAGE) else "").lower()
            show = not needle or (needle in pid or needle in name or needle in pkg)
            self.table.setRowHidden(r, not show)

    # -------------------------- Enable/disable logic -------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != self.COL_ENABLED:
            return

        source = item.data(self.ROLE_SOURCE)
        if source != "Installed":
            # catalog row: ignore toggles
            return

        pid = item.data(self.ROLE_PLUGIN_ID)
        if not pid:
            return

        enabled = item.checkState() == Qt.CheckState.Checked
        self._state.set_enabled(str(pid), enabled)

        if self._auto_reload_on_toggle:
            # Debounce reload: multiple toggles should cause only one reload.
            self._debounced_reload()

    def _debounced_reload(self) -> None:
        if self._reload_timer is None:
            self._reload_timer = QTimer(self)
            self._reload_timer.setSingleShot(True)
            self._reload_timer.timeout.connect(self._reload_plugins)

        self._reload_timer.start(200)

    # ----------------------------- Reload button -----------------------------

    def _on_reload(self) -> None:
        self._reload_plugins()
        QMessageBox.information(self, "Plugins", "Plugins reloaded.")

    # ----------------------------- Install/uninstall -------------------------

    def _on_action(self, plugin_id: str, action: str) -> None:
        pkg = self._pip_package_for(plugin_id)

        # fallback: if installed discovery provided package, use that
        if not pkg:
            pkg = self._installed_package_for(plugin_id)

        if not pkg:
            QMessageBox.critical(self, "Plugins", f"Cannot determine pip package for {plugin_id}.")
            return

        if action == "Install":
            self._run_pip(f"Installing {pkg}…", lambda: self._pip.install(pkg))
            return

        if action == "Uninstall":
            if QMessageBox.question(self, "Uninstall", f"Uninstall {pkg}?") != QMessageBox.StandardButton.Yes:
                return
            self._run_pip(f"Uninstalling {pkg}…", lambda: self._pip.uninstall(pkg))
            return

    def _pip_package_for(self, plugin_id: str) -> str | None:
        for c in self._catalog:
            if c.plugin_id == plugin_id:
                return c.pip_package
        return None

    def _installed_package_for(self, plugin_id: str) -> str | None:
        for p in self._get_installed():
            if p.plugin_id == plugin_id:
                pkg = getattr(p, "package", "") or ""
                return pkg or None
        return None

    def _run_pip(self, title: str, start: Callable[[], None]) -> None:
        """
        Runs pip operation via IPipInstaller, streaming output into PipProgressDialog.
        Ensures we do not leak Qt signal connections between runs.
        """
        dlg = PipProgressDialog(title, parent=self)

        def on_output(text: str) -> None:
            dlg.append(text)

        def on_finished(result: PipResult) -> None:
            try:
                if result.ok:
                    dlg.set_done(True, "Done.")
                else:
                    dlg.set_done(False, f"Failed (exit code {result.exit_code}). See log.")
                # Refresh list after operation
                self.refresh()
            finally:
                # IMPORTANT: disconnect to avoid duplicate callbacks on future runs
                try:
                    self._pip.output.disconnect(on_output)  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    self._pip.finished.disconnect(on_finished)  # type: ignore[attr-defined]
                except Exception:
                    pass

        # Connect signals for THIS run
        self._pip.output.connect(on_output)      # type: ignore[attr-defined]
        self._pip.finished.connect(on_finished)  # type: ignore[attr-defined]

        dlg.btn_cancel.clicked.connect(lambda: self._pip.cancel())
        dlg.btn_close.clicked.connect(dlg.accept)

        start()
        dlg.exec()