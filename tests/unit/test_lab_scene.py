from miniatured_world.activity import ActivityProviderStatus
from miniatured_world.app.lab import derive_lab_scene
from miniatured_world.app.snapshot import WorldSnapshot


def _snapshot(
    *,
    activity_level: str = "quiet",
    intensity: float = 0.0,
    materials: dict[str, int] | None = None,
    grid_materials: dict[str, int] | None = None,
    events: tuple[str, ...] = (),
    discoveries: tuple[str, ...] = (),
    running: bool = True,
    paused: bool = False,
) -> WorldSnapshot:
    return WorldSnapshot(
        seed=1,
        tendency="forest",
        traits=(),
        activity_level=activity_level,
        activity_intensity=intensity,
        running=running,
        paused=paused,
        world_visible=True,
        muted=False,
        activity_collection_enabled=True,
        provider_status=ActivityProviderStatus("demo", "デモ", True, True, "demo"),
        world_time=1.0,
        humidity=0.4,
        wind=0.1,
        temperature=0.5,
        materials=materials or {},
        grid_materials=grid_materials or {},
        plant_count=0,
        creature_count=0,
        events=events,
        discoveries=discoveries,
    )


def test_lab_scene_rests_when_activity_is_quiet() -> None:
    scene = derive_lab_scene(_snapshot())

    assert scene.character_state == "rest"
    assert scene.cauldron_state == "cauldron_idle"
    assert scene.caption == "静かに観察を続けています"


def test_lab_scene_works_when_activity_supplies_materials() -> None:
    scene = derive_lab_scene(
        _snapshot(
            activity_level="active",
            intensity=0.55,
            materials={"seed": 2, "water": 1},
            grid_materials={"seed": 2},
        )
    )

    assert scene.character_state == "work"
    assert scene.cauldron_state == "cauldron_receive"
    assert "material_drop" in scene.effects
    assert "reaction_light" in scene.effects
    assert scene.material_total == 3


def test_lab_scene_records_success_for_events_or_discoveries() -> None:
    scene = derive_lab_scene(
        _snapshot(
            activity_level="calm",
            intensity=0.2,
            materials={"soil": 1},
            events=("soft_rain",),
            discoveries=("first_rain",),
        )
    )

    assert scene.character_state == "success"
    assert scene.cauldron_state == "cauldron_success"
    assert scene.caption == "新しい反応を記録しました"


def test_lab_scene_does_not_expose_private_activity_content() -> None:
    scene = derive_lab_scene(
        _snapshot(activity_level="intense", intensity=0.9, materials={"mineral": 4})
    )

    serialized = repr(scene)
    forbidden = {"key_sequence", "window_title", "clipboard", "screen_capture", "mouse_x", "mouse_y"}
    assert all(term not in serialized for term in forbidden)
