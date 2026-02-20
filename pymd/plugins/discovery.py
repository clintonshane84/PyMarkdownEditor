from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib.metadata import entry_points, version

from pymd.plugins import ENTRYPOINT_GROUP


@dataclass(frozen=True)
class DiscoveredPlugin:
    factory: object
    entry_point_name: str
    dist_version: str | None


def discover_plugins() -> Iterable[DiscoveredPlugin]:
    eps = entry_points()
    group_eps = (
        eps.select(group=ENTRYPOINT_GROUP)
        if hasattr(eps, "select")
        else eps.get(ENTRYPOINT_GROUP, [])
    )
    for ep in group_eps:
        dist_ver: str | None = None
        try:
            # ep.dist is not always available across Python versions/tooling; best-effort.
            if getattr(ep, "dist", None) is not None:
                dist_ver = version(ep.dist.name)  # type: ignore[attr-defined]
        except Exception:
            dist_ver = None

        yield DiscoveredPlugin(
            factory=ep.load(),
            entry_point_name=ep.name,
            dist_version=dist_ver,
        )
