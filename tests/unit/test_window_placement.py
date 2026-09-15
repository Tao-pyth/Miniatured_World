from dataclasses import asdict, replace
import json

import pytest

from miniatured_world.app.service import MiniaturedWorldService
from miniatured_world.app.window_placement import fit_window
from miniatured_world.persistence.settings import Settings, WindowSettings
from miniatured_world.persistence.store import JsonStore


def test_negative_monitor_and_largest_intersection():
    saved = WindowSettings(True, -1100, 40, 960, 700)
    areas = [(0, 0, 1920, 1040), (-1280, 0, 1280, 984)]
    assert fit_window(saved, areas, frame=(8, 31, 8, 8)) == saved
    crossing = replace(saved, x=-600)
    assert fit_window(crossing, areas).x < 0


@pytest.mark.parametrize("saved", [WindowSettings(True, 3000, 2000, 960, 700), WindowSettings(True, -500, -300, 9000, 8000), WindowSettings()])
def test_missing_monitor_or_oversized_window_fits_small_primary(saved):
    area = (40, 25, 640, 450)
    placed = fit_window(saved, [area], frame=(8, 31, 8, 8))
    assert placed.saved
    assert 40 <= placed.x and placed.x + placed.width + 16 <= 680
    assert 25 <= placed.y and placed.y + placed.height + 39 <= 475
    assert placed.width > 0 and placed.height > 0


def test_empty_screen_list_does_not_invent_a_screen():
    saved = WindowSettings(True, 25, 25, 920, 640)
    assert fit_window(saved, []) == saved


def test_old_settings_without_placement_and_negative_coordinates_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"schema_version":1,"general":{"restore_window_position":true}}')
    store = JsonStore(tmp_path)
    settings = store.load_settings()
    assert settings.window == WindowSettings()
    changed = replace(settings, window=WindowSettings(True, -900, -100, 950, 650))
    store.save_settings(changed)
    assert JsonStore(tmp_path).load_settings() == changed


@pytest.mark.parametrize("window", [
    None, [], {"saved": 1}, {"saved": True}, {"saved": True, "width": False, "height": 650},
    {"saved": True, "width": 950, "height": -1}, {"saved": True, "width": 100001, "height": 650},
    {"saved": True, "width": 950, "height": 650, "x": 1000001},
    {"saved": True, "width": 950, "height": 650, "y": 1.0},
    {"saved": False, "x": 5}, {"other": True},
])
def test_invalid_placement_protects_original_settings(tmp_path, window):
    path = tmp_path / "settings.json"
    original = json.dumps({"schema_version": 1, "window": window}).encode()
    path.write_bytes(original)
    store = JsonStore(tmp_path)
    settings = store.load_settings()
    assert store.is_read_protected("settings.json")
    assert not settings.activity.enabled
    assert store.save_settings(Settings()) is None
    assert path.read_bytes() == original


@pytest.mark.parametrize("reason", ["save_off", "restore_off", "erased", "corrupt", "ephemeral"])
def test_automatic_placement_respects_save_boundaries(tmp_path, reason):
    if reason == "corrupt":
        (tmp_path / "settings.json").write_bytes(b"{broken fixture")
    service = MiniaturedWorldService.start(seed=1, data_root=None if reason == "ephemeral" else tmp_path)
    if reason == "save_off":
        service.update_setting("data", "save_settings", False)
    elif reason == "restore_off":
        service.update_setting("general", "restore_window_position", False)
    elif reason == "erased":
        assert service.delete_saved_data("settings")["settings.json"]
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    service.remember_window(WindowSettings(True, 40, 40, 1000, 650))
    service.retry_pending_saves(force=True)
    assert service.settings.window == WindowSettings()
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_explicit_resume_records_only_new_placement(tmp_path):
    service = MiniaturedWorldService.start(seed=1, data_root=tmp_path)
    service.remember_window(WindowSettings(True, 30, 30, 950, 630))
    service.delete_saved_data("settings")
    service.remember_window(WindowSettings(True, 50, 50, 960, 640))
    assert not (tmp_path / "settings.json").exists()
    service.update_setting("data", "save_settings", True)
    assert service.settings.window == WindowSettings()
    latest = WindowSettings(True, 70, 70, 980, 660)
    service.remember_window(latest)
    assert JsonStore(tmp_path).load_settings().window == latest
    assert set(asdict(latest)) == {"saved", "x", "y", "width", "height"}
