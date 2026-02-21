from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from pymd.app_bootstrapper import AppBootstrapper, BootstrapResult

# ----------------------------
# Fakes
# ----------------------------


@dataclass
class ProgressCall:
    kind: str
    payload: dict[str, Any]


class FakeProgress:
    def __init__(self) -> None:
        self.calls: list[ProgressCall] = []

    def set_status(self, text: str) -> None:
        self.calls.append(ProgressCall(kind="status", payload={"text": text}))

    def set_progress(self, *, value: int | None = None, maximum: int | None = None) -> None:
        self.calls.append(
            ProgressCall(kind="progress", payload={"value": value, "maximum": maximum})
        )


class FakePluginManager:
    def __init__(self, *, should_raise: bool = False) -> None:
        self.reload_called = 0
        self.should_raise = should_raise

    def reload(self) -> None:
        self.reload_called += 1
        if self.should_raise:
            raise RuntimeError("boom")


class FakeContainer:
    def __init__(
        self,
        *,
        window: object | None = None,
        plugin_manager: Any | None = None,
        build_raises: bool = False,
    ) -> None:
        self._window = window if window is not None else object()
        self._build_raises = build_raises
        if plugin_manager is not None:
            self.plugin_manager = plugin_manager  # matches hasattr(container, "plugin_manager")

        self.build_main_window_called = 0

    def build_main_window(self) -> object:
        self.build_main_window_called += 1
        if self._build_raises:
            raise RuntimeError("build failed")
        return self._window


# ----------------------------
# Tests
# ----------------------------


def test_boot_success_reports_progress_builds_window_and_reload_plugins(monkeypatch) -> None:
    progress = FakeProgress()
    pm = FakePluginManager(should_raise=False)
    container = FakeContainer(window=object(), plugin_manager=pm)

    boot = AppBootstrapper(progress=progress, delay_ms=2000)

    # avoid Qt event loop in tests
    monkeypatch.setattr(AppBootstrapper, "_intentional_delay", lambda self: None)

    result = boot.boot(container_factory=lambda: container)

    assert isinstance(result, BootstrapResult)
    assert result.window is container._window
    assert container.build_main_window_called == 1
    assert pm.reload_called == 1

    # Verify key progress/status sequencing (don't overfit)
    statuses = [c.payload["text"] for c in progress.calls if c.kind == "status"]
    assert statuses == [
        "Initializing…",
        "Loading services…",
        "Building interface…",
        "Loading plugins…",
        "Ready",
    ]

    # Verify progress calls include indeterminate then done
    progress_calls = [c.payload for c in progress.calls if c.kind == "progress"]
    assert progress_calls[0] == {"value": None, "maximum": None}  # indeterminate
    assert progress_calls[-1] == {"value": 1, "maximum": 1}  # done


def test_boot_plugin_reload_failure_is_swallowed_and_still_finishes(monkeypatch) -> None:
    progress = FakeProgress()
    pm = FakePluginManager(should_raise=True)
    container = FakeContainer(window=object(), plugin_manager=pm)

    boot = AppBootstrapper(progress=progress, delay_ms=0)
    monkeypatch.setattr(AppBootstrapper, "_intentional_delay", lambda self: None)

    result = boot.boot(container_factory=lambda: container)

    assert result.window is container._window
    assert container.build_main_window_called == 1
    assert pm.reload_called == 1

    # Must still reach Ready even if reload() explodes
    statuses = [c.payload["text"] for c in progress.calls if c.kind == "status"]
    assert statuses[-1] == "Ready"


def test_boot_container_factory_failure_propagates_and_reports_up_to_loading_services(
    monkeypatch,
) -> None:
    progress = FakeProgress()
    boot = AppBootstrapper(progress=progress, delay_ms=0)
    monkeypatch.setattr(AppBootstrapper, "_intentional_delay", lambda self: None)

    def bad_factory() -> object:
        raise RuntimeError("container init failed")

    with pytest.raises(RuntimeError, match="container init failed"):
        boot.boot(container_factory=bad_factory)

    # We should have at least set the earlier status messages before failing
    statuses = [c.payload["text"] for c in progress.calls if c.kind == "status"]
    assert statuses == ["Initializing…", "Loading services…"]


def test_boot_build_main_window_failure_propagates_and_reports_up_to_building_interface(
    monkeypatch,
) -> None:
    progress = FakeProgress()
    container = FakeContainer(build_raises=True)

    boot = AppBootstrapper(progress=progress, delay_ms=0)
    monkeypatch.setattr(AppBootstrapper, "_intentional_delay", lambda self: None)

    with pytest.raises(RuntimeError, match="build failed"):
        boot.boot(container_factory=lambda: container)

    statuses = [c.payload["text"] for c in progress.calls if c.kind == "status"]
    assert statuses == ["Initializing…", "Loading services…", "Building interface…"]
