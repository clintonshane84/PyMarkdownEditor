from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
import sys as _sys

import pytest

import pymd.app as app_mod


# ----------------------------
# Fakes (Qt)
# ----------------------------

class FakeQGuiApplication:
    set_attribute_calls: list[tuple[object, bool]] = []

    @classmethod
    def setAttribute(cls, attr: object, on: bool) -> None:
        cls.set_attribute_calls.append((attr, on))


class FakeQApplication:
    org_name: str | None = None
    app_name: str | None = None

    def __init__(self, argv: list[str]) -> None:
        self.argv = list(argv)
        self.process_events_called = 0
        self.exec_called = 0

    @classmethod
    def setOrganizationName(cls, name: str) -> None:
        cls.org_name = name

    @classmethod
    def setApplicationName(cls, name: str) -> None:
        cls.app_name = name

    def processEvents(self) -> None:
        self.process_events_called += 1

    def exec(self) -> int:
        self.exec_called += 1
        return 0


# ----------------------------
# Fakes (UI + boot)
# ----------------------------

class FakeSplashScreen:
    def __init__(self, *, image_path: Path, app_title: str) -> None:
        self.image_path = image_path
        self.app_title = app_title
        self.shown = False
        self.closed = False

    def show(self) -> None:
        self.shown = True

    def close(self) -> None:
        self.closed = True

    # progress protocol methods (bootstrapper expects these)
    def set_status(self, text: str) -> None:
        pass

    def set_progress(self, *, value: int | None = None, maximum: int | None = None) -> None:
        pass


class FakeWindow:
    def __init__(self) -> None:
        self.shown = False
        self.opened: Path | None = None

    def show(self) -> None:
        self.shown = True

    def _open_path(self, p: Path) -> None:
        self.opened = p


@dataclass(frozen=True)
class FakeBootstrapResult:
    window: object


class FakeBootstrapper:
    def __init__(self, *, progress: object) -> None:
        self.progress = progress
        self.boot_called = 0
        self.last_container_factory = None

    def boot(self, *, container_factory):
        self.boot_called += 1
        self.last_container_factory = container_factory
        container = container_factory()
        # mimic your real behavior: container builds a window
        w = container.build_main_window()
        return FakeBootstrapResult(window=w)


class FakeBootstrapperBoom(FakeBootstrapper):
    def boot(self, *, container_factory):
        raise RuntimeError("boot failed")


# ----------------------------
# Fakes (Container)
# ----------------------------

class FakeContainer:
    def __init__(self, *, window: FakeWindow | None = None) -> None:
        self.window = window or FakeWindow()
        self.build_main_window_called = 0
        self.build_args = None

    def build_main_window(self, *, start_path=None, app_title: str = "PyMarkdownEditor"):
        # fallback path passes these args; success path here is called without kwargs
        self.build_main_window_called += 1
        self.build_args = {"start_path": start_path, "app_title": app_title}
        return self.window


# ----------------------------
# Helpers to inject importable modules
# ----------------------------

def _install_fake_module(monkeypatch, name: str, **attrs) -> None:
    m = ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    monkeypatch.setitem(_sys.modules, name, m)


# ----------------------------
# Tests
# ----------------------------

def test_run_app_success_path_shows_splash_boots_and_shows_window(monkeypatch, tmp_path: Path) -> None:
    # Patch Qt entrypoints used by app.py
    monkeypatch.setattr(app_mod, "QGuiApplication", FakeQGuiApplication)
    monkeypatch.setattr(app_mod, "QApplication", FakeQApplication)

    # Ensure resource path is deterministic + exists (SplashScreen always receives it)
    splash_path = tmp_path / "assets" / "splash.png"
    splash_path.parent.mkdir(parents=True, exist_ok=True)
    splash_path.write_bytes(b"fake")  # doesn't matter; SplashScreen fake doesn't load it
    monkeypatch.setattr(app_mod, "_resource_path", lambda rel: splash_path)

    # Inject modules imported inside try:
    _install_fake_module(monkeypatch, "pymd.services.ui.splash_screen", SplashScreen=FakeSplashScreen)
    _install_fake_module(monkeypatch, "pymd.app_bootstrapper", AppBootstrapper=FakeBootstrapper)

    # Patch Container.default
    container = FakeContainer()
    monkeypatch.setattr(app_mod.Container, "default", staticmethod(lambda: container))

    # Provide argv with a start_path, ensure it is passed into _open_path when supported
    file_to_open = tmp_path / "doc.md"
    file_to_open.write_text("# hi", encoding="utf-8")

    rc = app_mod.run_app(["pymd", str(file_to_open)])

    assert rc == 0

    # Splash created + shown + closed
    # (we can recover it via the bootstrapper progress reference)
    # easiest: check that the window was shown and open called; splash close implied by no exception.
    assert container.window.shown is True
    assert container.window.opened == file_to_open

    # Bootstrapper was used (called once)
    # We can infer by: build_main_window called once with no kwargs (success path),
    # and also by: start_path was opened via _open_path instead of container.build_main_window(start_path=...)
    assert container.build_main_window_called == 1

    # QApplication wiring happened
    assert FakeQApplication.org_name == app_mod.APP_ORG
    assert FakeQApplication.app_name == app_mod.APP_NAME

    # SetAttribute called (we don’t assert exact enum object, just that it was invoked)
    assert FakeQGuiApplication.set_attribute_calls, "QGuiApplication.setAttribute was not called"


def test_run_app_fallback_path_when_bootstrapper_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_mod, "QGuiApplication", FakeQGuiApplication)
    monkeypatch.setattr(app_mod, "QApplication", FakeQApplication)

    splash_path = tmp_path / "assets" / "splash.png"
    splash_path.parent.mkdir(parents=True, exist_ok=True)
    splash_path.write_bytes(b"fake")
    monkeypatch.setattr(app_mod, "_resource_path", lambda rel: splash_path)

    # Inject splash + a bootstrapper that raises on boot()
    _install_fake_module(monkeypatch, "pymd.services.ui.splash_screen", SplashScreen=FakeSplashScreen)
    _install_fake_module(monkeypatch, "pymd.app_bootstrapper", AppBootstrapper=FakeBootstrapperBoom)

    # Two containers: one for try-path, one for fallback (because your code calls Container.default() again)
    try_container = FakeContainer(window=FakeWindow())
    fallback_container = FakeContainer(window=FakeWindow())

    calls = {"n": 0}

    def _default():
        calls["n"] += 1
        return try_container if calls["n"] == 1 else fallback_container

    monkeypatch.setattr(app_mod.Container, "default", staticmethod(_default))

    file_to_open = tmp_path / "doc.md"
    file_to_open.write_text("x", encoding="utf-8")

    rc = app_mod.run_app(["pymd", str(file_to_open)])

    assert rc == 0

    # Fallback path uses container.build_main_window(start_path=..., app_title=APP_NAME)
    assert fallback_container.build_main_window_called == 1
    assert fallback_container.build_args == {
        "start_path": file_to_open,
        "app_title": app_mod.APP_NAME,
    }
    assert fallback_container.window.shown is True

    # In fallback path, we do NOT call win._open_path manually (that's in success path)
    assert fallback_container.window.opened is None


def test_resource_path_dev_points_to_repo_root_assets(monkeypatch, tmp_path: Path) -> None:
    """
    Dev mode: repo_root = parent of package folder (pymd).
    We patch __file__ resolution by monkeypatching Path(__file__).resolve().parent.parent indirectly
    via monkeypatching app_mod.__file__.
    """
    # Make a fake structure:
    # tmp_path/repo/pymd/app.py (pretend)
    repo = tmp_path / "repo"
    pkg = repo / "pymd"
    pkg.mkdir(parents=True)
    fake_app_py = pkg / "app.py"
    fake_app_py.write_text("x")

    monkeypatch.setattr(app_mod, "__file__", str(fake_app_py))
    monkeypatch.setattr(app_mod.sys, "frozen", False, raising=False)
    if hasattr(app_mod.sys, "_MEIPASS"):
        monkeypatch.delattr(app_mod.sys, "_MEIPASS", raising=False)

    p = app_mod._resource_path("assets/splash.png")
    assert p == repo / "assets" / "splash.png"


def test_resource_path_pyinstaller_uses_meipass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_mod.sys, "_MEIPASS", str(tmp_path), raising=False)

    p = app_mod._resource_path("assets/splash.png")
    assert p == tmp_path / "assets" / "splash.png"
