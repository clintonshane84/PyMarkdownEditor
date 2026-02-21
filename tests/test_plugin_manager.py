from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pymd.plugins.manager as manager_mod
from pymd.plugins.manager import PluginManager


# ------------------------------
# Test doubles
# ------------------------------


@dataclass(frozen=True)
class _Meta:
    id: str
    name: str
    version: str
    description: str


class _StateStore:
    """Minimal IPluginStateStore double."""

    def __init__(self, enabled: dict[str, bool] | None = None) -> None:
        self._enabled = dict(enabled or {})

    def get_enabled(self, plugin_id: str, *, default: bool = False) -> bool:
        return bool(self._enabled.get(plugin_id, default))

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self._enabled[plugin_id] = bool(enabled)

    def all_states(self) -> dict[str, bool]:
        return dict(self._enabled)


class _Api:
    """Minimal IAppAPI double."""
    pass


class _PluginOK:
    def __init__(self, pid: str, *, actions: Iterable[tuple[Any, Any]] | None = None) -> None:
        self.meta = _Meta(pid, f"Plugin {pid}", "1.0.0", f"desc {pid}")
        self._actions = list(actions or [])
        self.activated_with: Any | None = None
        self.deactivated: bool = False

    def activate(self, api: Any) -> None:
        self.activated_with = api

    def deactivate(self) -> None:
        self.deactivated = True

    def register_actions(self):
        return list(self._actions)


class _PluginWithHooks(_PluginOK):
    def __init__(self, pid: str) -> None:
        super().__init__(pid)
        self.on_load_calls: int = 0
        self.on_ready_calls: int = 0

    def on_load(self, api: Any) -> None:
        self.on_load_calls += 1

    def on_ready(self, api: Any) -> None:
        self.on_ready_calls += 1


class _PluginOnLoadBoom(_PluginWithHooks):
    def on_load(self, api: Any) -> None:
        self.on_load_calls += 1
        raise RuntimeError("on_load failed")


class _PluginOnReadyBoom(_PluginWithHooks):
    def on_ready(self, api: Any) -> None:
        self.on_ready_calls += 1
        raise RuntimeError("on_ready failed")


class _PluginActivateBoom(_PluginOK):
    def activate(self, api: Any) -> None:
        raise RuntimeError("activate failed")


class _PluginActionsBoom(_PluginOK):
    def register_actions(self):
        raise RuntimeError("register_actions failed")


@dataclass(frozen=True)
class _Discovered:
    factory: object
    entry_point_name: str = "x"
    dist_version: str | None = None


# ------------------------------
# Tests
# ------------------------------


def test_discover_and_list_plugins_skips_broken_factories(monkeypatch):
    good = _PluginOK("good")

    def bad_factory():
        raise RuntimeError("broken factory")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [_Discovered(factory=lambda: good), _Discovered(factory=bad_factory)],
        raising=True,
    )

    pm = PluginManager(state=_StateStore())
    pm.discover()

    rows = pm.list_plugins()
    assert len(rows) == 1
    assert rows[0].plugin_id == "good"
    assert rows[0].name == "Plugin good"
    assert rows[0].version == "1.0.0"
    assert rows[0].description == "desc good"


def test_reload_activates_enabled_plugins_and_skips_activation_failures(monkeypatch):
    ok = _PluginOK("ok")
    boom = _PluginActivateBoom("boom")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [_Discovered(factory=lambda: ok), _Discovered(factory=lambda: boom)],
        raising=True,
    )

    state = _StateStore({"ok": True, "boom": True})
    api = _Api()

    pm = PluginManager(state=state, api=api)
    pm.reload()

    assert ok.activated_with is api
    assert boom.activated_with is None

    assert "ok" in pm._active
    assert "boom" not in pm._active


def test_reload_deactivates_when_disabled_and_resets_ready_once(monkeypatch):
    ok = _PluginWithHooks("ok")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [_Discovered(factory=lambda: ok)],
        raising=True,
    )

    state = _StateStore({"ok": True})
    api = _Api()
    pm = PluginManager(state=state, api=api)

    pm.reload()
    assert "ok" in pm._active

    # ready should run once per activation session
    pm.on_app_ready()
    pm.on_app_ready()
    assert ok.on_ready_calls == 1

    # disable and reload -> deactivate + reset ready session
    state.set_enabled("ok", False)
    pm.reload()
    assert ok.deactivated is True
    assert "ok" not in pm._active

    # re-enable -> activate again
    state.set_enabled("ok", True)
    pm.reload()
    assert "ok" in pm._active

    # ready should be allowed again for the new activation session
    pm.on_app_ready()
    assert ok.on_ready_calls == 2


def test_reload_clears_active_when_api_missing(monkeypatch):
    ok = _PluginOK("ok")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [_Discovered(factory=lambda: ok)],
        raising=True,
    )

    state = _StateStore({"ok": True})
    pm = PluginManager(state=state, api=None)

    pm._active["ok"] = ok
    pm.reload()

    assert pm._active == {}


def test_iter_enabled_actions_success_and_failure_paths(monkeypatch):
    called: dict[str, int] = {"ok": 0}

    @dataclass(frozen=True)
    class Spec:
        title: str = "Do Thing"
        shortcut: str | None = None
        status_tip: str | None = None

    def handler(api: Any) -> None:
        assert isinstance(api, _Api)
        called["ok"] += 1

    ok_actions = _PluginOK("ok", actions=[(Spec(), handler)])
    bad_actions = _PluginActionsBoom("bad_actions")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [
            _Discovered(factory=lambda: ok_actions),
            _Discovered(factory=lambda: bad_actions),
        ],
        raising=True,
    )

    state = _StateStore({"ok": True, "bad_actions": True})
    api = _Api()

    pm = PluginManager(state=state)
    actions = pm.iter_enabled_actions(api)

    assert len(actions) == 1

    spec, fn = actions[0]
    assert spec.title == "Do Thing"

    fn(api)
    assert called["ok"] == 1

    state.set_enabled("ok", False)
    actions2 = pm.iter_enabled_actions(api)
    assert actions2 == []


def test_on_load_runs_once_per_process_even_across_disable_enable(monkeypatch):
    p = _PluginWithHooks("p")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [_Discovered(factory=lambda: p)],
        raising=True,
    )

    state = _StateStore({"p": True})
    api = _Api()
    pm = PluginManager(state=state, api=api)

    pm.reload()
    assert p.on_load_calls == 1
    assert "p" in pm._active

    # disable -> deactivate
    state.set_enabled("p", False)
    pm.reload()
    assert "p" not in pm._active

    # re-enable within same process: on_load should NOT run again
    state.set_enabled("p", True)
    pm.reload()
    assert p.on_load_calls == 1


def test_on_load_failure_is_swallowed_and_still_marked_once(monkeypatch):
    p = _PluginOnLoadBoom("p")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [_Discovered(factory=lambda: p)],
        raising=True,
    )

    state = _StateStore({"p": True})
    api = _Api()
    pm = PluginManager(state=state, api=api)

    # should not raise
    pm.reload()
    assert p.on_load_calls == 1
    assert "p" in pm._active

    # subsequent reload should not call on_load again
    pm.reload()
    assert p.on_load_calls == 1


def test_on_ready_failure_is_swallowed_and_marked_once_per_session(monkeypatch):
    p = _PluginOnReadyBoom("p")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [_Discovered(factory=lambda: p)],
        raising=True,
    )

    state = _StateStore({"p": True})
    api = _Api()
    pm = PluginManager(state=state, api=api)

    pm.reload()
    pm.on_app_ready()
    pm.on_app_ready()

    # even though it throws, it should only attempt once per activation session
    assert p.on_ready_calls == 1

    # disable -> reset session
    state.set_enabled("p", False)
    pm.reload()
    state.set_enabled("p", True)
    pm.reload()

    pm.on_app_ready()
    assert p.on_ready_calls == 2
