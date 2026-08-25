from pathlib import Path

from miniatured_world.persistence.paths import default_data_root


def test_default_data_root_can_be_overridden(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MINIATURED_WORLD_DATA_DIR", str(tmp_path))

    assert default_data_root() == tmp_path


def test_default_data_root_prefers_local_app_data(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("MINIATURED_WORLD_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_data_root() == Path(tmp_path) / "MiniaturedWorld"

