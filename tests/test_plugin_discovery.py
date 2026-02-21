# tests/test_plugin_discovery.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pymd.plugins.discovery as discovery_mod


# ----------------------------
# Fakes
# ----------------------------


@dataclass
class FakeDist:
    name: str


class FakeEntryPoint:
    def __init__(
        self,
        *,
        name: str,
        factory: object,
        dist: FakeDist | None = None,
            load_raises: Exception | None = None,
    ) -> None:
        self.name = name
        self.dist = dist
        self._factory = factory
        self._load_raises = load_raises
        self.loaded = False

    def load(self) -> object:
        if self._load_raises is not None:
            raise self._load_raises
        self.loaded = True
        return self._factory


class FakeEntryPointsWithSelect:
    """Mimics importlib.metadata.EntryPoints that supports .select(group=...)."""

    def __init__(self, *, group: str, eps: list[FakeEntryPoint]) -> None:
        self._group = group
        self._eps = eps

    def select(self, *, group: str) -> list[FakeEntryPoint]:
        return list(self._eps) if group == self._group else []


class FakeEntryPointsLegacy(dict):
    """Legacy mapping-style entry_points() return value with .get(group, [])."""


# ----------------------------
# Tests
# ----------------------------


def test_discover_plugins_unified_includes_builtins_first_then_entrypoints_select_path(monkeypatch):
    g = discovery_mod.ENTRYPOINT_GROUP

    # ---- builtins ----
    builtin1 = discovery_mod.DiscoveredPlugin(
        factory=object(), entry_point_name="builtin:one", dist_version=None
    )
    builtin2 = discovery_mod.DiscoveredPlugin(
        factory=object(), entry_point_name="builtin:two", dist_version=None
    )

    monkeypatch.setattr(
        discovery_mod,
        "_discover_builtin_plugins",
        lambda: iter([builtin1, builtin2]),
        raising=True,
    )

    # ---- entry points (.select path) ----
    f1 = object()
    f2 = object()
    ep1 = FakeEntryPoint(name="plugA", factory=f1, dist=FakeDist("distA"))
    ep2 = FakeEntryPoint(name="plugB", factory=f2, dist=FakeDist("distB"))

    fake_eps = FakeEntryPointsWithSelect(group=g, eps=[ep1, ep2])

    def fake_entry_points() -> Any:
        return fake_eps

    def fake_version(dist_name: str) -> str:
        assert dist_name in ("distA", "distB")
        return "9.9.9"

    monkeypatch.setattr(discovery_mod, "entry_points", fake_entry_points, raising=True)
    monkeypatch.setattr(discovery_mod, "version", fake_version, raising=True)

    out = list(discovery_mod.discover_plugins())

    # builtins first
    assert len(out) == 4
    assert out[0].entry_point_name == "builtin:one"
    assert out[0].dist_version is None
    assert out[1].entry_point_name == "builtin:two"
    assert out[1].dist_version is None

    # entry points next
    assert ep1.loaded is True
    assert ep2.loaded is True

    assert out[2].entry_point_name == "plugA"
    assert out[2].factory is f1
    assert out[2].dist_version == "9.9.9"

    assert out[3].entry_point_name == "plugB"
    assert out[3].factory is f2
    assert out[3].dist_version == "9.9.9"


def test_discover_plugins_legacy_get_path_and_version_failure(monkeypatch):
    g = discovery_mod.ENTRYPOINT_GROUP

    # no builtins for this test
    monkeypatch.setattr(discovery_mod, "_discover_builtin_plugins", lambda: iter(()), raising=True)

    f = object()
    ep = FakeEntryPoint(name="plugX", factory=f, dist=FakeDist("distX"))
    fake_eps = FakeEntryPointsLegacy({g: [ep]})

    def fake_entry_points() -> Any:
        return fake_eps

    def boom_version(_: str) -> str:
        raise RuntimeError("no version info")

    monkeypatch.setattr(discovery_mod, "entry_points", fake_entry_points, raising=True)
    monkeypatch.setattr(discovery_mod, "version", boom_version, raising=True)

    out = list(discovery_mod.discover_plugins())

    assert len(out) == 1
    assert ep.loaded is True

    row = out[0]
    assert row.entry_point_name == "plugX"
    assert row.factory is f
    assert row.dist_version is None


def test_discover_plugins_skips_broken_entrypoint_load(monkeypatch):
    g = discovery_mod.ENTRYPOINT_GROUP

    # no builtins for this test
    monkeypatch.setattr(discovery_mod, "_discover_builtin_plugins", lambda: iter(()), raising=True)

    good_factory = object()
    ep_good = FakeEntryPoint(name="good", factory=good_factory, dist=FakeDist("distGood"))
    ep_bad = FakeEntryPoint(
        name="bad",
        factory=object(),
        dist=FakeDist("distBad"),
        load_raises=RuntimeError("broken load"),
    )

    fake_eps = FakeEntryPointsWithSelect(group=g, eps=[ep_bad, ep_good])

    def fake_entry_points() -> Any:
        return fake_eps

    def fake_version(dist_name: str) -> str:
        # even if version is available, bad load should skip plugin entirely
        return "1.2.3"

    monkeypatch.setattr(discovery_mod, "entry_points", fake_entry_points, raising=True)
    monkeypatch.setattr(discovery_mod, "version", fake_version, raising=True)

    out = list(discovery_mod.discover_plugins())

    assert len(out) == 1
    assert out[0].entry_point_name == "good"
    assert out[0].factory is good_factory
    assert out[0].dist_version == "1.2.3"
    assert ep_bad.loaded is False
    assert ep_good.loaded is True
