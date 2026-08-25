from miniatured_world.app.service import MiniaturedWorldService


def test_service_smoke_cycle_persists_safe_state(tmp_path) -> None:
    service = MiniaturedWorldService.start(seed=20260825, data_root=tmp_path)

    for index in range(5):
        service.inject_demo_activity(index)
        service.step()

    text = service.summary_text()
    assert "Miniatured World" in text
    assert "発見=" in text
    assert (tmp_path / "settings.json").exists()
    assert (tmp_path / "discovery.json").exists()
