from miniatured_world.content import load_default_catalog


def test_default_content_catalog_is_valid() -> None:
    catalog = load_default_catalog()

    assert catalog.schema_version == 1
    assert "soil" in catalog.materials
    assert catalog.tendencies
    assert catalog.traits
    assert catalog.plants
    assert catalog.creatures
    assert catalog.events

