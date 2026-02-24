# tests/test_ini_config_service.py
from __future__ import annotations

from pathlib import Path

import pytest

from pymd.services.config.ini_config_service import IniConfigService


def _write_ini(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ------------------------------
# Load order + loaded_from
# ------------------------------
def test_loads_from_explicit_path_success(tmp_path: Path):
    ini = tmp_path / "explicit.ini"
    _write_ini(
        ini,
        """
[app]
version = 1.2.3

[ui]
wrap = true
font_size = 14
""".strip(),
    )

    svc = IniConfigService(explicit_path=ini, project_root=None)

    assert svc.loaded_from == ini
    assert svc.app_version() == "1.2.3"
    assert svc.get_bool("ui", "wrap") is True
    assert svc.get_int("ui", "font_size") == 14


def test_explicit_missing_falls_back_to_project_root_success(tmp_path: Path):
    # Explicit path does not exist
    missing = tmp_path / "missing.ini"

    project_root = tmp_path / "repo"
    project_ini = project_root / "config" / "config.ini"
    _write_ini(
        project_ini,
        """
[app]
version = 9.9.9
""".strip(),
    )

    svc = IniConfigService(explicit_path=missing, project_root=project_root)

    assert svc.loaded_from == project_ini
    assert svc.app_version() == "9.9.9"


def test_malformed_explicit_is_ignored_then_uses_project_root(tmp_path: Path, monkeypatch):
    """
    Fail path: read_file raises -> should not crash; it should continue and load next candidate.
    """
    bad = tmp_path / "bad.ini"
    _write_ini(bad, "[app]\nversion = 1.0.0\n")

    project_root = tmp_path / "repo"
    good = project_root / "config" / "config.ini"
    _write_ini(good, "[app]\nversion = 2.0.0\n")

    # Force any attempt to open the explicit file to raise.
    real_open = Path.open

    def open_boom(self: Path, *a, **k):
        if self == bad:
            raise OSError("boom")
        return real_open(self, *a, **k)

    monkeypatch.setattr(Path, "open", open_boom, raising=True)

    svc = IniConfigService(explicit_path=bad, project_root=project_root)

    assert svc.loaded_from == good
    assert svc.app_version() == "2.0.0"


def test_no_files_found_sets_safe_defaults(tmp_path: Path, monkeypatch):
    """
    Fail path: nothing exists -> safe defaults must be present.
    We also set HOME to isolate fallback candidate.
    """
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    svc = IniConfigService(explicit_path=None, project_root=None)

    assert svc.loaded_from is None
    assert svc.app_version() == "0.0.0"
    assert svc.get("app", "version") == "0.0.0"


# ------------------------------
# get / get_int / get_bool success & fail paths
# ------------------------------
def test_get_returns_default_for_missing_section_and_key(tmp_path: Path):
    ini = tmp_path / "x.ini"
    _write_ini(ini, "[app]\nversion = 1.0.0\n")
    svc = IniConfigService(explicit_path=ini)

    assert svc.get("missing", "k", "d") == "d"
    assert svc.get("app", "missing", "d2") == "d2"


def test_get_int_success_and_fail_paths(tmp_path: Path):
    ini = tmp_path / "x.ini"
    _write_ini(
        ini,
        """
[ui]
font_size = 16
bad_int = sixteen
""".strip(),
    )
    svc = IniConfigService(explicit_path=ini)

    assert svc.get_int("ui", "font_size") == 16  # success
    assert svc.get_int("ui", "bad_int", 12) == 12  # fail -> default
    assert svc.get_int("ui", "missing", 11) == 11  # missing -> default
    assert svc.get_int("missing", "x", 10) == 10  # missing section -> default


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        ("y", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("No", False),
        ("n", False),
        ("off", False),
    ],
)
def test_get_bool_truthy_falsy_success(tmp_path: Path, raw: str, expected: bool):
    ini = tmp_path / "x.ini"
    _write_ini(ini, f"[ui]\nflag = {raw}\n")
    svc = IniConfigService(explicit_path=ini)

    assert svc.get_bool("ui", "flag") is expected


def test_get_bool_fail_path_unknown_value_returns_default(tmp_path: Path):
    ini = tmp_path / "x.ini"
    _write_ini(ini, "[ui]\nflag = maybe\n")
    svc = IniConfigService(explicit_path=ini)

    assert svc.get_bool("ui", "flag", default=True) is True
    assert svc.get_bool("ui", "flag", default=False) is False


# ------------------------------
# as_dict + app_version behaviour
# ------------------------------
def test_as_dict_returns_snapshot_copy(tmp_path: Path):
    ini = tmp_path / "x.ini"
    _write_ini(
        ini,
        """
[app]
version = 3.3.3

[ui]
wrap = true
""".strip(),
    )
    svc = IniConfigService(explicit_path=ini)

    d = svc.as_dict()
    assert d["app"]["version"] == "3.3.3"
    assert d["ui"]["wrap"] == "true"

    # ensure snapshot is a copy, not live view
    d["ui"]["wrap"] = "false"
    assert svc.get("ui", "wrap") == "true"


def test_app_version_falls_back_to_default_when_empty_or_missing(tmp_path: Path):
    # version key missing -> default injected
    ini1 = tmp_path / "missing_version.ini"
    _write_ini(ini1, "[app]\nname = x\n")
    svc1 = IniConfigService(explicit_path=ini1)
    assert svc1.app_version() == "0.0.0"

    # version empty -> returns default '0.0.0' due to 'or "0.0.0"'
    ini2 = tmp_path / "empty_version.ini"
    _write_ini(ini2, "[app]\nversion =\n")
    svc2 = IniConfigService(explicit_path=ini2)
    assert svc2.app_version() == "0.0.0"


# ------------------------------
# Optional: platformdirs fallback path (HOME/.config/...)
# ------------------------------
def test_fallback_home_config_path_used_when_no_platformdirs(tmp_path: Path, monkeypatch):
    """
    Forces the 'no platformdirs' branch by patching module-level user_config_dir to None,
    then verifies HOME/.config/PyMarkdownEditor/config.ini is discovered.
    """
    # Import module to patch its symbol
    import pymd.services.config.ini_config_service as mod

    monkeypatch.setattr(mod, "user_config_dir", None, raising=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    expected = tmp_path / "home" / ".config" / "PyMarkdownEditor" / "config.ini"
    _write_ini(expected, "[app]\nversion = 7.7.7\n")

    svc = IniConfigService(explicit_path=None, project_root=None)

    assert svc.loaded_from == expected
    assert svc.app_version() == "7.7.7"
