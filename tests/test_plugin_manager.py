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

    def get_enabled(self, plugin_id: str, default: bool = False) -> bool:
        return self._enabled.get(plugin_id, default)

    def set_enabled(self, plugin_id: str, value: bool) -> None:
        self._enabled[plugin_id] = value


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


class _PluginActivateBoom(_PluginOK):
    def activate(self, api: Any) -> None:
        raise RuntimeError("activate failed")


class _PluginActionsBoom(_PluginOK):
    def register_actions(self):
        raise RuntimeError("register_actions failed")


# ------------------------------
# Tests
# ------------------------------


def test_discover_and_list_plugins_skips_broken_factories(monkeypatch):
    good = _PluginOK("good")

    def bad_factory():
        raise RuntimeError("broken factory")

    # discover_plugins() returns factories OR instances; manager supports both
    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [lambda: good, bad_factory],
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
        lambda: [lambda: ok, lambda: boom],
        raising=True,
    )

    state = _StateStore({"ok": True, "boom": True})
    api = _Api()

    pm = PluginManager(state=state, api=api)
    pm.reload()

    # ok activated
    assert ok.activated_with is api

    # boom didn't activate and should not crash reload
    assert boom.activated_with is None

    # internal active set should contain ok but not boom
    assert "ok" in pm._active
    assert "boom" not in pm._active


def test_reload_deactivates_when_disabled(monkeypatch):
    ok = _PluginOK("ok")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [lambda: ok],
        raising=True,
    )

    state = _StateStore({"ok": True})
    api = _Api()
    pm = PluginManager(state=state, api=api)

    pm.reload()
    assert "ok" in pm._active
    assert ok.deactivated is False

    # now disable and reload: should deactivate
    state.set_enabled("ok", False)
    pm.reload()

    assert ok.deactivated is True
    assert "ok" not in pm._active


def test_reload_clears_active_when_api_missing(monkeypatch):
    ok = _PluginOK("ok")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [lambda: ok],
        raising=True,
    )

    state = _StateStore({"ok": True})
    pm = PluginManager(state=state, api=None)

    # even if enabled, without api it should not activate and should clear active
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
        # ensure wrapper passes through the api object
        assert isinstance(api, _Api)
        called["ok"] += 1

    ok_actions = _PluginOK("ok", actions=[(Spec(), handler)])
    bad_actions = _PluginActionsBoom("bad_actions")

    monkeypatch.setattr(
        manager_mod,
        "discover_plugins",
        lambda: [lambda: ok_actions, lambda: bad_actions],
        raising=True,
    )

    state = _StateStore({"ok": True, "bad_actions": True})
    api = _Api()

    pm = PluginManager(state=state)
    actions = pm.iter_enabled_actions(api)

    # bad_actions plugin should be skipped (register_actions throws)
    assert len(actions) == 1

    spec, fn = actions[0]
    assert spec.title == "Do Thing"

    # execute returned wrapper
    fn(api)
    assert called["ok"] == 1

    # disabled plugins should not contribute actions
    state.set_enabled("ok", False)
    actions2 = pm.iter_enabled_actions(api)
    assert actions2 == []
