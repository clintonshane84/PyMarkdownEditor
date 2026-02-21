from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

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
    ) -> None:
        self.name = name
        self.dist = dist
        self._factory = factory
        self.loaded = False

    def load(self) -> object:
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

def test_discover_plugins_success_select_path(monkeypatch):
    # Arrange
    g = discovery_mod.ENTRYPOINT_GROUP

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

    monkeypatch.setattr(discovery_mod, "entry_points", fake_entry_points)
    monkeypatch.setattr(discovery_mod, "version", fake_version)

    # Act
    out = list(discovery_mod.discover_plugins())

    # Assert
    assert len(out) == 2
    assert ep1.loaded is True
    assert ep2.loaded is True

    assert out[0].entry_point_name == "plugA"
    assert out[0].factory is f1
    assert out[0].dist_version == "9.9.9"

    assert out[1].entry_point_name == "plugB"
    assert out[1].factory is f2
    assert out[1].dist_version == "9.9.9"


def test_discover_plugins_fail_version_and_legacy_get_path(monkeypatch):
    # Arrange
    g = discovery_mod.ENTRYPOINT_GROUP

    f = object()
    ep = FakeEntryPoint(name="plugX", factory=f, dist=FakeDist("distX"))

    fake_eps = FakeEntryPointsLegacy({g: [ep]})

    def fake_entry_points() -> Any:
        return fake_eps

    def boom_version(_: str) -> str:
        raise RuntimeError("no version info")

    monkeypatch.setattr(discovery_mod, "entry_points", fake_entry_points)
    monkeypatch.setattr(discovery_mod, "version", boom_version)

    # Act
    out = list(discovery_mod.discover_plugins())

    # Assert
    assert len(out) == 1
    assert ep.loaded is True

    row = out[0]
    assert row.entry_point_name == "plugX"
    assert row.factory is f
    # fail path: version lookup error should yield None
    assert row.dist_version is None
