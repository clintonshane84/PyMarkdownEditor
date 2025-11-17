# tests/test_ini_config_service.py
from __future__ import annotations

from pathlib import Path
import os
import io
import pytest

from pymd.services.config.ini_config_service import IniConfigService


def write_ini(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_defaults_when_no_config_files(monkeypatch, tmp_path):
    # Ensure no platformdirs and no home fallback file
    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir", None, raising=False
    )
    monkeypatch.setenv("HOME", str(tmp_path))  # make sure fallback resolves to empty home

    cfg = IniConfigService()
    assert cfg.app_version() == "0.0.0"
    assert cfg.loaded_from is None

    # getters with defaults
    assert cfg.get("missing", "key", "x") == "x"
    assert cfg.get_int("app", "nonint", 42) == 42
    assert cfg.get_bool("app", "nope", False) is False
    assert isinstance(cfg.as_dict(), dict)


def test_project_root_config_is_used_when_present(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir", None, raising=False
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    proj_root = tmp_path / "repo"
    ini = proj_root / "config" / "config.ini"
    write_ini(
        ini,
        "[app]\nversion = 1.2.3\n[ui]\nwrap = true\n",
    )

    cfg = IniConfigService(project_root=proj_root)
    assert cfg.app_version() == "1.2.3"
    assert cfg.get_bool("ui", "wrap", None) is True
    assert cfg.loaded_from == ini


def test_platformdirs_preferred_over_project_root(monkeypatch, tmp_path):
    # Simulate platformdirs is available and returns a user config directory
    def fake_user_config_dir(appname: str) -> str:
        # ~/.config/<app> equivalent under tmp
        return str(tmp_path / "usercfg")

    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir",
        fake_user_config_dir,
        raising=False,
    )

    # Create both files; platformdirs one should win
    plat_path = Path(fake_user_config_dir(IniConfigService.DEFAULT_APP_DIR)) / IniConfigService.DEFAULT_FILE
    proj_root = tmp_path / "repo"
    proj_path = proj_root / "config" / "config.ini"

    write_ini(plat_path, "[app]\nversion = 2.0.0\n")
    write_ini(proj_path, "[app]\nversion = 1.0.0\n")

    cfg = IniConfigService(project_root=proj_root)
    assert cfg.app_version() == "2.0.0"
    assert cfg.loaded_from == plat_path


def test_explicit_path_overrides_everything(monkeypatch, tmp_path):
    # Arrange a platformdirs file and a project file AND an explicit file
    def fake_user_config_dir(appname: str) -> str:
        return str(tmp_path / "usercfg")

    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir",
        fake_user_config_dir,
        raising=False,
    )

    plat_path = Path(fake_user_config_dir(IniConfigService.DEFAULT_APP_DIR)) / IniConfigService.DEFAULT_FILE
    proj_root = tmp_path / "repo"
    proj_path = proj_root / "config" / "config.ini"
    explicit_path = tmp_path / "explicit.ini"

    write_ini(plat_path, "[app]\nversion = 2.0.0\n")
    write_ini(proj_path, "[app]\nversion = 1.0.0\n")
    write_ini(explicit_path, "[app]\nversion = 9.9.9\n")

    cfg = IniConfigService(explicit_path=explicit_path, project_root=proj_root)
    assert cfg.app_version() == "9.9.9"
    assert cfg.loaded_from == explicit_path


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("42", 42),
        ("  7  ", 7),
        ("notanint", None),
        ("", None),
    ],
)
def test_get_int_parsing(monkeypatch, tmp_path, raw, expected):
    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir", None, raising=False
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    ini = tmp_path / ".config" / IniConfigService.DEFAULT_APP_DIR / IniConfigService.DEFAULT_FILE
    write_ini(ini, f"[limits]\nmax = {raw}\n")

    cfg = IniConfigService()
    assert cfg.get_int("limits", "max", None) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("true", True),
        (" True ", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("no", False),
        ("off", False),
        ("0", False),
        ("maybe", None),
        ("", None),
    ],
)
def test_get_bool_parsing(monkeypatch, tmp_path, raw, expected):
    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir", None, raising=False
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    ini = tmp_path / ".config" / IniConfigService.DEFAULT_APP_DIR / IniConfigService.DEFAULT_FILE
    write_ini(ini, f"[feature]\nenabled = {raw}\n")

    cfg = IniConfigService()
    assert cfg.get_bool("feature", "enabled", None) is expected


def test_as_dict_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir", None, raising=False
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    ini = tmp_path / ".config" / IniConfigService.DEFAULT_APP_DIR / IniConfigService.DEFAULT_FILE
    write_ini(
        ini,
        "[app]\nversion = 3.1.4\n\n[ui]\nwrap = true\nzoom = 110\n",
    )

    cfg = IniConfigService()
    snap = cfg.as_dict()
    # Sections defined are present with their items; version should be as configured
    assert snap.get("app", {}).get("version") == "3.1.4"
    assert snap.get("ui", {}).get("wrap") == "true"
    assert snap.get("ui", {}).get("zoom") == "110"


def test_malformed_config_is_ignored_and_defaults_used(monkeypatch, tmp_path):
    # Force platformdirs path and write garbage there
    def fake_user_config_dir(appname: str) -> str:
        return str(tmp_path / "usercfg")

    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir",
        fake_user_config_dir,
        raising=False,
    )
    bad_path = Path(fake_user_config_dir(IniConfigService.DEFAULT_APP_DIR)) / IniConfigService.DEFAULT_FILE
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("this is not INI at all", encoding="utf-8")

    cfg = IniConfigService()
    # It should not crash, loaded_from stays None, and defaults applied
    assert cfg.loaded_from is None
    assert cfg.app_version() == "0.0.0"


def test_home_fallback_used_when_platformdirs_missing(monkeypatch, tmp_path):
    # No platformdirs
    monkeypatch.setattr(
        "pymd.services.config.ini_config_service.user_config_dir", None, raising=False
    )
    # Point HOME to tmp so fallback path is predictable
    monkeypatch.setenv("HOME", str(tmp_path))

    # Create ~/.config/PyMarkdownEditor/config.ini
    fb_path = tmp_path / ".config" / IniConfigService.DEFAULT_APP_DIR / IniConfigService.DEFAULT_FILE
    write_ini(fb_path, "[app]\nversion = 4.5.6\n")

    cfg = IniConfigService()
    assert cfg.app_version() == "4.5.6"
    assert cfg.loaded_from == fb_path
