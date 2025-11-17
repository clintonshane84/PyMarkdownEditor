# pymd/services/config/ini_config_service.py
from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Optional, Mapping, Dict

try:
    # Prefer modern community standard
    from platformdirs import user_config_dir  # type: ignore
except Exception:
    user_config_dir = None  # optional fallback

from pymd.domain.interfaces import IConfigService


class IniConfigService(IConfigService):
    r"""
    INI-backed configuration reader.

    Load order (first hit wins):
      1. Explicit path provided at construction
      2. User config dir (e.g., ~/.config/PyMarkdownEditor/config.ini or %APPDATA%\PyMarkdownEditor\config.ini)
      3. Project default at <repo>/config/config.ini  (optional)
    """

    DEFAULT_APP_DIR = "PyMarkdownEditor"
    DEFAULT_FILE = "config.ini"

    def __init__(self, explicit_path: Optional[Path] = None, project_root: Optional[Path] = None):
        self._parser = configparser.ConfigParser()
        self._loaded_from: Optional[Path] = None

        # Resolve candidates
        candidates: list[Path] = []
        if explicit_path:
            candidates.append(explicit_path)

        # ~/.config/PyMarkdownEditor/config.ini (Linux) or OS equivalent via platformdirs
        if user_config_dir:
            cfg_dir = Path(user_config_dir(self.DEFAULT_APP_DIR))
            candidates.append(cfg_dir / self.DEFAULT_FILE)
        else:
            # very light fallback
            home = Path(os.path.expanduser("~"))
            candidates.append(home / ".config" / self.DEFAULT_APP_DIR / self.DEFAULT_FILE)

        # Repo default (optional, handy for dev)
        if project_root:
            candidates.append(project_root / "config" / self.DEFAULT_FILE)

        # Load first existing file
        for path in candidates:
            try:
                if path and path.exists():
                    with path.open("r", encoding="utf-8") as fh:
                        self._parser.read_file(fh)
                    self._loaded_from = path
                    break
            except Exception:
                # Don't crash the app due to malformed config—app can still run with defaults.
                continue

        # Provide safe defaults if file not found
        if "app" not in self._parser:
            self._parser["app"] = {}
        self._parser["app"].setdefault("version", "0.0.0")  # first key requested

    # ----- IConfigService -----

    def get(self, section: str, key: str, default: Optional[str] = None) -> Optional[str]:
        if section not in self._parser:
            return default
        return self._parser[section].get(key, default)

    def get_int(self, section: str, key: str, default: Optional[int] = None) -> Optional[int]:
        val = self.get(section, key, None)
        if val is None:
            return default
        try:
            return int(val.strip())
        except Exception:
            return default

    def get_bool(self, section: str, key: str, default: Optional[bool] = None) -> Optional[bool]:
        val = self.get(section, key, None)
        if val is None:
            return default
        truth = {"1", "true", "yes", "y", "on"}
        falsy = {"0", "false", "no", "n", "off"}
        s = val.strip().lower()
        if s in truth:
            return True
        if s in falsy:
            return False
        return default

    def as_dict(self) -> Mapping[str, Mapping[str, str]]:
        snap: Dict[str, Dict[str, str]] = {}
        for sect in self._parser.sections():
            snap[sect] = dict(self._parser[sect])  # copy
        return snap

    def app_version(self) -> str:
        return self.get("app", "version", "0.0.0") or "0.0.0"

    # ----- Extras -----

    @property
    def loaded_from(self) -> Optional[Path]:
        """For diagnostics/About dialog."""
        return self._loaded_from
