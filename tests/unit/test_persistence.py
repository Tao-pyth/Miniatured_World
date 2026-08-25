import json

from miniatured_world.persistence import DiscoveryRecord, JsonStore, Settings


def test_json_store_saves_privacy_safe_files(tmp_path) -> None:
    store = JsonStore(tmp_path)

    store.save_settings(Settings())
    store.save_discovery(DiscoveryRecord(discoveries=["plant:sprout", "quiet_night", "plant:sprout"]))

    settings = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    discovery = json.loads((tmp_path / "discovery.json").read_text(encoding="utf-8"))
    combined = json.dumps({"settings": settings, "discovery": discovery}, ensure_ascii=False)

    assert store.load_settings().schema_version == 1
    assert store.load_discovery().discoveries == ["plant:sprout", "quiet_night"]
    for sensitive_sample in ("super_secret_password", "A B C", "x=100", "y=200", "Window Title"):
        assert sensitive_sample not in combined


def test_settings_categories_cover_specification() -> None:
    settings = Settings()

    assert settings.general.language == "ja"
    assert settings.display.view_mode == "window"
    assert settings.activity.frame_window_ms == 1000
    assert settings.sound.enabled is True
    assert settings.notifications.discovery_enabled is True
    assert settings.privacy.store_raw_input is False
    assert settings.performance.max_particles > 0
    assert settings.data.save_discovery is True
