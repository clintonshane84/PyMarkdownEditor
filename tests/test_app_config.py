# tests/test_app_config.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pymd.services.config.app_config import AppConfig, build_app_config


# ------------------------------
# Helpers
# ------------------------------
def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class FakeIni:
    """
    Minimal IniConfigService-like fake with controllable behaviour.
    We only implement what AppConfig calls.
    """

    def __init__(self, *, version: str = "0.0.0", loaded_from: Path | None = None) -> None:
        self._version = version
        self._loaded_from = loaded_from

    def app_version(self) -> str:
        return self._version

    def get(self, section: str, key: str, default: str | None = None) -> str | None:
        return default

    def get_int(self, section: str, key: str, default: int | None = None) -> int | None:
        return default

    def get_bool(self, section: str, key: str, default: bool | None = None) -> bool | None:
        return default

    def as_dict(self) -> dict[str, dict[str, str]]:
        return {"app": {"version": self._version}}

    @property
    def loaded_from(self) -> Path | None:
        return self._loaded_from


# ------------------------------
# get_version(): success paths
# ------------------------------
def test_get_version_prefers_version_file_and_strips_v(tmp_path: Path):
    root = tmp_path / "proj"
    _write(root / "version", "v1.0.5\n")
    cfg = AppConfig(ini=FakeIni(version="9.9.9"), project_root=root)

    assert cfg.get_version() == "1.0.5"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.2.3", "1.2.3"),
        ("v1.2.3", "1.2.3"),
        ("V1.2.3", "1.2.3"),
        ("v1.2.3+build.7", "1.2.3"),
        ("1.2.3-alpha.1", "1.2.3"),
    ],
)
def test_get_version_parses_semver_with_suffixes(tmp_path: Path, raw: str, expected: str):
    root = tmp_path / "proj"
    _write(root / "version", raw)
    cfg = AppConfig(ini=FakeIni(version="0.0.0"), project_root=root)

    assert cfg.get_version() == expected


def test_get_version_falls_back_to_ini_when_version_file_missing(tmp_path: Path):
    root = tmp_path / "proj"
    cfg = AppConfig(ini=FakeIni(version="v2.3.4"), project_root=root)

    assert cfg.get_version() == "2.3.4"


def test_get_version_falls_back_to_ini_when_version_file_invalid(tmp_path: Path):
    root = tmp_path / "proj"
    _write(root / "version", "not-a-version")
    cfg = AppConfig(ini=FakeIni(version="2.0.1"), project_root=root)

    assert cfg.get_version() == "2.0.1"


# ------------------------------
# get_version(): fail paths
# ------------------------------
def test_get_version_returns_0_0_0_when_version_file_unreadable_and_ini_empty(tmp_path: Path):
    root = tmp_path / "proj"
    # no version file present, ini returns empty/whitespace
    cfg = AppConfig(ini=FakeIni(version="   "), project_root=root)

    assert cfg.get_version() == "0.0.0"


def test_get_version_returns_ini_raw_if_ini_version_is_non_semver(tmp_path: Path):
    """
    If ini app_version is non-empty but doesn't match semver, AppConfig returns it as-is.
    """
    root = tmp_path / "proj"
    cfg = AppConfig(ini=FakeIni(version="dev"), project_root=root)

    assert cfg.get_version() == "dev"


# ------------------------------
# Delegation / passthrough
# ------------------------------
def test_loaded_from_delegates_to_ini(tmp_path: Path):
    ini_path = tmp_path / "settings.ini"
    cfg = AppConfig(ini=FakeIni(version="1.0.0", loaded_from=ini_path), project_root=tmp_path)
    assert cfg.loaded_from == ini_path


def test_as_dict_delegates_to_ini(tmp_path: Path):
    cfg = AppConfig(ini=FakeIni(version="3.3.3"), project_root=tmp_path)
    d = cfg.as_dict()
    assert d["app"]["version"] == "3.3.3"


# ------------------------------
# build_app_config(): integration-ish checks
# ------------------------------
def test_build_app_config_uses_supplied_project_root_and_reads_version_file(tmp_path: Path):
    root = tmp_path / "repo"
    _write(root / "version", "v4.5.6")

    cfg = build_app_config(project_root=root)
    assert cfg.project_root == root
    assert cfg.get_version() == "4.5.6"


def test_build_app_config_passes_explicit_ini_path(tmp_path: Path):
    root = tmp_path / "repo"
    _write(root / "version", "v1.0.0")

    explicit_ini = tmp_path / "explicit.ini"
    _write(explicit_ini, "[app]\nversion = 9.9.9\n")

    cfg = build_app_config(explicit_ini=explicit_ini, project_root=root)

    # We don't reach into IniConfigService internals other than loaded_from,
    # which is explicitly exposed for diagnostics.
    assert cfg.loaded_from == explicit_ini
    # version file still wins
    assert cfg.get_version() == "1.0.0"
