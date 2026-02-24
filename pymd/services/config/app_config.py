from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pymd.domain.interfaces import IAppConfig
from pymd.services.config.ini_config_service import IniConfigService

_VERSION_RE = re.compile(r"^v?(\d+\.\d+\.\d+)(?:[-+].*)?$", re.IGNORECASE)


def _project_root_fallback() -> Path:
    """
    Best-effort project root resolution that also works in PyInstaller:
      - PyInstaller onefile/onedir uses sys._MEIPASS as bundle root
      - dev mode uses this file location to walk upward
    """
    meipass = getattr(sys, "_MEIPASS", None)  # type: ignore[attr-defined]
    if meipass:
        return Path(meipass)

    # app_config.py -> pymd/services/config/app_config.py
    # parents[3] = repository root (same trick you used in about.py)
    return Path(__file__).resolve().parents[3]


def _read_version_file(version_path: Path) -> str | None:
    try:
        raw = version_path.read_text(encoding="utf-8").strip()
    except Exception:
        return None

    m = _VERSION_RE.match(raw)
    if not m:
        return None

    # return normalized X.Y.Z (no leading v)
    return m.group(1)


@dataclass(frozen=True)
class AppConfig(IAppConfig):
    """
    Adapter that wraps IniConfigService and adds get_version() from <root>/version file.

    Precedence for version:
      1) <project_root>/version file (semantic e.g. v1.0.5)
      2) ini_config_service.app_version() (fallback)
      3) "0.0.0"
    """

    ini: IniConfigService
    project_root: Path

    def get_version(self) -> str:
        v = _read_version_file(self.project_root / "version")
        if v:
            return v

        # fallback to ini setting (kept for compatibility / override scenarios)
        v2 = self.ini.app_version()
        v2 = (v2 or "").strip()
        if v2:
            # normalize possible "v1.0.5"
            m = _VERSION_RE.match(v2)
            return m.group(1) if m else v2

        return "0.0.0"

    # ---- delegate IniConfigService methods (full surface) ----

    def get(self, section: str, key: str, default: str | None = None) -> str | None:
        return self.ini.get(section, key, default)

    def get_int(self, section: str, key: str, default: int | None = None) -> int | None:
        return self.ini.get_int(section, key, default)

    def get_bool(self, section: str, key: str, default: bool | None = None) -> bool | None:
        return self.ini.get_bool(section, key, default)

    def as_dict(self) -> Mapping[str, Mapping[str, str]]:
        return self.ini.as_dict()

    def app_version(self) -> str:
        return self.ini.app_version()

    @property
    def loaded_from(self) -> Path | None:
        return self.ini.loaded_from


def build_app_config(
    *, explicit_ini: Path | None = None, project_root: Path | None = None
) -> AppConfig:
    root = project_root or _project_root_fallback()
    ini = IniConfigService(explicit_path=explicit_ini, project_root=root)
    return AppConfig(ini=ini, project_root=root)
