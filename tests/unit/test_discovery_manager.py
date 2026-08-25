from miniatured_world.persistence import DiscoveryManager, JsonStore


def test_discovery_manager_merges_deduplicates_and_persists(tmp_path) -> None:
    store = JsonStore(tmp_path)
    manager = DiscoveryManager.load(store)

    record = manager.merge(["rainbow", "plant:sprout", "rainbow"])
    loaded = DiscoveryManager.load(store)

    assert record.discoveries == ["plant:sprout", "rainbow"]
    assert loaded.discoveries == {"plant:sprout", "rainbow"}

