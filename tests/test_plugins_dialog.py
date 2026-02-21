from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import pytest
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QPushButton, QTableWidgetItem
from PyQt6.QtTest import QSignalSpy

import pymd.services.ui.plugins_dialog as dlg_mod
from pymd.plugins.pip_installer import PipResult


# ----------------------------
# Fakes
# ----------------------------

class FakeStateStore:
    def __init__(self) -> None:
        self._m: dict[str, bool] = {}
        self.calls: list[tuple[str, bool]] = []

    def get_enabled(self, plugin_id: str, *, default: bool = False) -> bool:
        return bool(self._m.get(plugin_id, default))

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self._m[str(plugin_id)] = bool(enabled)
        self.calls.append((str(plugin_id), bool(enabled)))

    def all_states(self) -> dict[str, bool]:
        return dict(self._m)


class FakePipWithSignals(QObject):
    output = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.installs: list[str] = []
        self.uninstalls: list[str] = []
        self.cancels = 0

    def install(self, package: str) -> None:
        self.installs.append(package)

    def uninstall(self, package: str) -> None:
        self.uninstalls.append(package)

    def cancel(self) -> None:
        self.cancels += 1


class FakePipNoSignals:
    """No Qt signals -> should hit fail path in _run_pip()."""

    def install(self, package: str) -> None:  # pragma: no cover
        raise AssertionError("should not be called")

    def uninstall(self, package: str) -> None:  # pragma: no cover
        raise AssertionError("should not be called")

    def cancel(self) -> None:
        pass


class FakeProgressDialog:
    """
    Non-modal stand-in for PipProgressDialog.
    dlg.exec() returns immediately (avoids test hang).
    """

    def __init__(self, title: str, parent=None) -> None:
        self.title = title
        self.parent = parent
        self.lines: list[str] = []
        self.done: tuple[bool, str] | None = None

        self.btn_cancel = QPushButton("Cancel")
        self.btn_close = QPushButton("Close")

    def append(self, text: str) -> None:
        self.lines.append(text)

    def set_done(self, ok: bool, message: str) -> None:
        self.done = (bool(ok), str(message))

    def accept(self) -> None:
        return

    def exec(self) -> int:
        # Non-blocking replacement
        return 0


@dataclass(frozen=True)
class FakeCatalogItem:
    plugin_id: str
    name: str
    description: str
    pip_package: str


# ----------------------------
# Helpers
# ----------------------------

def _cell_button(table, row: int, col: int) -> QPushButton:
    w = table.cellWidget(row, col)
    assert isinstance(w, QPushButton)
    return w


# ----------------------------
# Tests
# ----------------------------

def test_plugins_dialog_refresh_toggle_and_reload_success(qapp, monkeypatch):
    # Patch modal dialogs so tests never block
    monkeypatch.setattr(dlg_mod.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(dlg_mod.QMessageBox, "critical", lambda *a, **k: None)

    # Make reload timer fire immediately when started
    def _instant_start(self, *_a, **_k):
        self.timeout.emit()

    monkeypatch.setattr(dlg_mod.QTimer, "start", _instant_start, raising=False)

    state = FakeStateStore()
    pip = FakePipWithSignals()

    reload_called = {"n": 0}

    def reload_plugins() -> None:
        reload_called["n"] += 1

    installed_rows = [
        dlg_mod.InstalledPluginRow(
            plugin_id="p.installed",
            name="InstalledPlugin",
            version="1.0",
            description="Installed desc",
            package="installed-pkg",
        )
    ]

    def get_installed() -> Sequence[dlg_mod.InstalledPluginRow]:
        return installed_rows

    catalog = [
        FakeCatalogItem(
            plugin_id="p.catalog",
            name="CatalogPlugin",
            description="Catalog desc",
            pip_package="catalog-pkg",
        ),
    ]

    # Patch catalog type expectations (the dialog only reads attributes)
    d = dlg_mod.PluginsDialog(
        parent=None,
        state=state,
        pip=pip,  # type: ignore[arg-type]
        get_installed=get_installed,
        reload_plugins=reload_plugins,
        catalog=catalog,  # type: ignore[arg-type]
        auto_reload_on_toggle=True,
    )
    d.show()
    qapp.processEvents()

    # refresh() happens in __init__ -> table should have installed + catalog rows
    assert d.table.rowCount() == 2

    # Find installed row and toggle enabled
    # Installed row has Source == "Installed"
    installed_row_index = None
    for r in range(d.table.rowCount()):
        src = d.table.item(r, d.COL_SOURCE).text()
        if src == "Installed":
            installed_row_index = r
            break
    assert installed_row_index is not None

    enabled_item: QTableWidgetItem = d.table.item(installed_row_index, d.COL_ENABLED)
    assert enabled_item is not None

    # Simulate user checking the box
    enabled_item.setCheckState(Qt.CheckState.Checked)
    d._on_item_changed(enabled_item)
    qapp.processEvents()

    assert state.calls[-1] == ("p.installed", True)
    # auto reload should fire immediately (we patched start())
    assert reload_called["n"] >= 1


def test_plugins_dialog_install_and_uninstall_success_and_fail(qapp, monkeypatch):
    # Patch PipProgressDialog to a non-blocking fake
    monkeypatch.setattr(dlg_mod, "PipProgressDialog", FakeProgressDialog)

    # Patch message boxes
    info_called = {"n": 0}
    crit_called = {"n": 0}
    monkeypatch.setattr(dlg_mod.QMessageBox, "information",
                        lambda *a, **k: info_called.__setitem__("n", info_called["n"] + 1))
    monkeypatch.setattr(dlg_mod.QMessageBox, "critical",
                        lambda *a, **k: crit_called.__setitem__("n", crit_called["n"] + 1))

    # Uninstall confirmation: Yes
    monkeypatch.setattr(dlg_mod.QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    state = FakeStateStore()
    pip = FakePipWithSignals()

    reload_called = {"n": 0}

    def reload_plugins() -> None:
        reload_called["n"] += 1

    installed_rows = [
        dlg_mod.InstalledPluginRow(
            plugin_id="p.installed",
            name="InstalledPlugin",
            version="1.0",
            description="Installed desc",
            package="installed-pkg",
        )
    ]

    def get_installed() -> Sequence[dlg_mod.InstalledPluginRow]:
        return installed_rows

    catalog = [
        FakeCatalogItem(
            plugin_id="p.catalog",
            name="CatalogPlugin",
            description="Catalog desc",
            pip_package="catalog-pkg",
        ),
    ]

    d = dlg_mod.PluginsDialog(
        parent=None,
        state=state,
        pip=pip,  # type: ignore[arg-type]
        get_installed=get_installed,
        reload_plugins=reload_plugins,
        catalog=catalog,  # type: ignore[arg-type]
        auto_reload_on_toggle=False,
    )
    d.show()
    qapp.processEvents()

    # Identify catalog row and click Install
    catalog_row_index = None
    for r in range(d.table.rowCount()):
        src = d.table.item(r, d.COL_SOURCE).text()
        pid = d.table.item(r, d.COL_PLUGIN_ID).text()
        if src == "Catalog" and pid == "p.catalog":
            catalog_row_index = r
            break
    assert catalog_row_index is not None

    btn_install = _cell_button(d.table, catalog_row_index, d.COL_ACTION)
    assert btn_install.text() == "Install"

    # Trigger action; this calls _run_pip which connects signals and calls pip.install(...)
    btn_install.click()
    qapp.processEvents()

    assert pip.installs == ["catalog-pkg"]

    # Stream output and finish OK
    pip.output.emit("Collecting...\n")
    pip.finished.emit(PipResult(ok=True, exit_code=0, stdout="ok", stderr=""))
    qapp.processEvents()

    # Identify installed row and click Uninstall
    installed_row_index = None
    for r in range(d.table.rowCount()):
        src = d.table.item(r, d.COL_SOURCE).text()
        pid = d.table.item(r, d.COL_PLUGIN_ID).text()
        if src == "Installed" and pid == "p.installed":
            installed_row_index = r
            break
    assert installed_row_index is not None

    btn_uninstall = _cell_button(d.table, installed_row_index, d.COL_ACTION)
    assert btn_uninstall.text() == "Uninstall"

    btn_uninstall.click()
    qapp.processEvents()

    assert pip.uninstalls == ["installed-pkg"]

    # Finish FAIL path
    pip.finished.emit(PipResult(ok=False, exit_code=7, stdout="", stderr="boom"))
    qapp.processEvents()

    # No critical in this flow (it shows done message in dialog + refresh)
    assert crit_called["n"] == 0


def test_plugins_dialog_fail_when_no_package_and_fail_when_no_pip_signals(qapp, monkeypatch):
    # Patch message boxes
    crit_called = {"n": 0}
    monkeypatch.setattr(dlg_mod.QMessageBox, "critical",
                        lambda *a, **k: crit_called.__setitem__("n", crit_called["n"] + 1))
    monkeypatch.setattr(dlg_mod.QMessageBox, "information", lambda *a, **k: None)

    state = FakeStateStore()

    # Case 1: cannot determine package (no catalog match and installed.package empty)
    pip = FakePipWithSignals()

    installed_rows = [
        dlg_mod.InstalledPluginRow(
            plugin_id="p.unknown",
            name="Unknown",
            version="1.0",
            description="",
            package="",  # no package available
        )
    ]

    def get_installed() -> Sequence[dlg_mod.InstalledPluginRow]:
        return installed_rows

    d1 = dlg_mod.PluginsDialog(
        parent=None,
        state=state,
        pip=pip,  # type: ignore[arg-type]
        get_installed=get_installed,
        reload_plugins=lambda: None,
        catalog=[],  # no catalog either
        auto_reload_on_toggle=False,
    )
    d1.show()
    qapp.processEvents()

    # Find the installed row and click action (will be "—" because no uninstall package)
    # But we can call _on_action directly to hit the fail path reliably:
    d1._on_action("p.unknown", "Uninstall")
    qapp.processEvents()
    assert crit_called["n"] >= 1

    # Case 2: pip has no signals -> _run_pip should critical
    d2 = dlg_mod.PluginsDialog(
        parent=None,
        state=state,
        pip=FakePipNoSignals(),  # type: ignore[arg-type]
        get_installed=lambda: [],
        reload_plugins=lambda: None,
        catalog=[
            FakeCatalogItem(
                plugin_id="p.catalog",
                name="CatalogPlugin",
                description="",
                pip_package="catalog-pkg",
            )
        ],  # type: ignore[arg-type]
        auto_reload_on_toggle=False,
    )
    d2.show()
    qapp.processEvents()

    d2._on_action("p.catalog", "Install")
    qapp.processEvents()
    assert crit_called["n"] >= 2


def test_plugins_dialog_uninstall_cancelled_does_not_call_pip(qapp, monkeypatch):
    monkeypatch.setattr(dlg_mod, "PipProgressDialog", FakeProgressDialog)
    monkeypatch.setattr(dlg_mod.QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(dlg_mod.QMessageBox, "information", lambda *a, **k: None)

    # Uninstall confirmation: No
    monkeypatch.setattr(dlg_mod.QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    state = FakeStateStore()
    pip = FakePipWithSignals()

    installed_rows = [
        dlg_mod.InstalledPluginRow(
            plugin_id="p.installed",
            name="InstalledPlugin",
            version="1.0",
            description="",
            package="installed-pkg",
        )
    ]

    d = dlg_mod.PluginsDialog(
        parent=None,
        state=state,
        pip=pip,  # type: ignore[arg-type]
        get_installed=lambda: installed_rows,
        reload_plugins=lambda: None,
        catalog=[],
        auto_reload_on_toggle=False,
    )
    d.show()
    qapp.processEvents()

    d._on_action("p.installed", "Uninstall")
    qapp.processEvents()

    assert pip.uninstalls == []
