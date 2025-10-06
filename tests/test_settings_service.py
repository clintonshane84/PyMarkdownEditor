from pymd.services.settings_service import SettingsService


def test_settings_roundtrip_geometry(settings_service: SettingsService):
    blob = b"\x01\x02\x03"
    settings_service.set_geometry(blob)
    got = settings_service.get_geometry()
    assert isinstance(got, (bytes, bytearray))
    assert bytes(got) == blob


def test_settings_roundtrip_splitter(settings_service: SettingsService):
    blob = b"\xaa\xbb"
    settings_service.set_splitter(blob)
    got = settings_service.get_splitter()
    assert isinstance(got, (bytes, bytearray))
    assert bytes(got) == blob


def test_settings_recents(settings_service: SettingsService):
    assert settings_service.get_recent() == []  # default
    r = ["a.md", "b.md"]
    settings_service.set_recent(r)
    assert settings_service.get_recent() == r
