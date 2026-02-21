from __future__ import annotations

import json

from pymd.plugins.state import SETTINGS_PLUGINS_ENABLED, SettingsPluginStateStore


def test_state_store_default_when_missing(settings_service):
    store = SettingsPluginStateStore(settings=settings_service)

    # no key yet -> defaults apply
    assert store.get_enabled("p1") is False
    assert store.get_enabled("p1", default=True) is True
    assert store.all_states() == {}


def test_state_store_set_and_get_roundtrip_persists_map(settings_service):
    store = SettingsPluginStateStore(settings=settings_service)

    store.set_enabled("p1", True)
    store.set_enabled("p2", False)

    assert store.get_enabled("p1") is True
    assert store.get_enabled("p2") is False
    assert store.all_states() == {"p1": True, "p2": False}

    # verify it actually wrote JSON to underlying settings
    raw = settings_service.get_raw(SETTINGS_PLUGINS_ENABLED, "")
    assert isinstance(raw, str)
    decoded = json.loads(raw)
    assert decoded == {"p1": True, "p2": False}


def test_state_store_updates_existing_map(settings_service):
    store = SettingsPluginStateStore(settings=settings_service)

    store.set_enabled("p1", True)
    store.set_enabled("p1", False)  # overwrite

    assert store.get_enabled("p1") is False
    assert store.all_states() == {"p1": False}


def test_state_store_handles_corrupt_json_gracefully(settings_service):
    # simulate corruption / manual edits
    settings_service.set_raw(SETTINGS_PLUGINS_ENABLED, "{not:json")

    store = SettingsPluginStateStore(settings=settings_service)

    # should not crash; should fall back to empty map
    assert store.all_states() == {}
    assert store.get_enabled("p1") is False
    assert store.get_enabled("p1", default=True) is True


def test_state_store_handles_non_string_raw_value(settings_service, monkeypatch):
    store = SettingsPluginStateStore(settings=settings_service)

    # Force get_raw to return non-string (unexpected type)
    monkeypatch.setattr(settings_service, "get_raw", lambda *a, **k: 123)

    assert store.all_states() == {}
    assert store.get_enabled("p1") is False
    assert store.get_enabled("p1", default=True) is True
