from dataclasses import replace

from miniatured_world.activity import ActivityProviderStatus
from miniatured_world.app.lab import CYCLE_MS, WORKFLOW, LabAnimation, derive_lab_scene, material_transfer_progress
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
        ),
        reaction=True,
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


def test_animation_loops_without_activity_updates_and_freezes_on_pause() -> None:
    animation = LabAnimation()
    snapshot = _snapshot(activity_level="active", intensity=0.5, materials={"seed": 2})
    animation.observe(snapshot)
    frames = []
    for _ in range(9):
        frames.append(animation.frame_index)
        animation.advance(125)
    assert frames == [0, 1, 2, 3, 4, 5, 6, 7, 0]
    animation.observe(replace(snapshot, paused=True))
    before = animation.elapsed_ms
    animation.advance(2000)
    assert animation.elapsed_ms == before
    assert animation.scene.character_state == "rest"
    assert animation.scene.effects == ()
    animation.observe(replace(snapshot, world_visible=False))
    animation.advance(2000)
    assert animation.elapsed_ms == before
    animation.observe(snapshot)
    animation.advance(125)
    assert animation.elapsed_ms == before + 125


def test_success_is_transient_and_saved_discoveries_do_not_retrigger_it() -> None:
    animation = LabAnimation()
    snapshot = _snapshot(activity_level="active", intensity=0.5, materials={"seed": 2}, discoveries=("old",))
    animation.observe(snapshot)
    assert animation.scene.character_state == "work"
    new = replace(snapshot, discoveries=("old", "new"), world_time=2)
    animation.observe(new)
    assert animation.scene.character_state == "success"
    animation.advance(3200)
    animation.observe(new)
    assert animation.scene.character_state == "work"
    animation.observe(replace(new, events=("rain",), world_time=3))
    assert animation.scene.character_state == "success"
    animation.observe(replace(snapshot, seed=2))
    assert animation.scene.character_state == "work"


def test_quiet_inventory_does_not_keep_materials_flying() -> None:
    scene = derive_lab_scene(_snapshot(materials={"seed": 3}, grid_materials={"seed": 2}, discoveries=("old",)))
    assert scene.character_state == "rest"
    assert "material_drop" not in scene.effects
    empty = derive_lab_scene(_snapshot(activity_level="intense", intensity=0.9))
    assert "material_drop" not in empty.effects


def test_material_delivery_completes_ordered_workflow_without_changing_world() -> None:
    animation = LabAnimation()
    before = _snapshot(activity_level="active", intensity=0.5)
    after = replace(before, materials={"seed": 1, "water": 1}, world_time=2)
    animation.observe(before)
    animation.observe(after)
    states = []
    for phase, duration in WORKFLOW:
        scene = animation.scene
        assert scene.workflow_phase == phase
        assert scene.phase_progress == 0
        states.append({item.placement.key: item.state for item in scene.gimmicks})
        animation.advance(duration)
    assert states[0]["basket"] == "arriving"
    assert states[1]["book"] == "turning"
    assert states[2]["basket"] == "taking"
    assert states[3]["cauldron"] == "cauldron_receive"
    assert states[4]["product"] == "placing"
    assert animation.scene.workflow_phase == "idle"
    assert animation.scene.product_visible
    assert before.materials == {}
    assert after.materials == {"seed": 1, "water": 1}
    assert after.discoveries == ()


def test_continuous_activity_coalesces_deliveries_without_restarting_reading() -> None:
    animation = LabAnimation()
    snapshot = _snapshot(activity_level="active", intensity=0.5)
    animation.observe(snapshot)
    animation.observe(replace(snapshot, materials={"seed": 1}))
    animation.advance(1800)
    progress = animation.scene.phase_progress
    for count in range(2, 30):
        current = replace(snapshot, materials={"seed": count}, world_time=count)
        animation.observe(current)
        animation.observe(current)
    assert animation.scene.workflow_phase == "read"
    assert animation.scene.phase_progress == progress
    animation.advance(CYCLE_MS - 1800)
    assert animation.scene.workflow_phase == "arrive"
    assert animation.scene.product_visible
    animation.advance(CYCLE_MS)
    assert animation.scene.workflow_phase == "idle"
    animation.advance(CYCLE_MS)
    assert animation.scene.workflow_phase == "idle"


def test_workflow_pause_visibility_and_session_reset() -> None:
    animation = LabAnimation()
    base = _snapshot(activity_level="active", intensity=0.5)
    delivered = replace(base, materials={"mineral": 1}, world_time=2)
    animation.observe(base)
    animation.observe(delivered)
    animation.advance(1900)
    reading = animation.scene
    animation.observe(replace(delivered, paused=True))
    animation.advance(2000)
    assert animation.scene.character_state == "rest"
    animation.observe(replace(delivered, world_visible=False))
    animation.advance(2000)
    animation.observe(delivered)
    assert animation.scene == reading
    animation.observe(replace(delivered, seed=2))
    assert animation.scene.workflow_phase == "idle"
    assert not animation.scene.product_visible
    assert animation.scene.batch_materials == ()


def test_inventory_decrease_and_disabled_collection_do_not_start_delivery() -> None:
    animation = LabAnimation()
    base = _snapshot(materials={"seed": 4}, discoveries=("saved",))
    animation.observe(base)
    assert animation.scene.workflow_phase == "idle"
    animation.observe(replace(base, materials={"seed": 3}, world_time=2))
    assert animation.scene.workflow_phase == "idle"
    animation.observe(replace(base, materials={"seed": 8}, world_time=3, activity_collection_enabled=False))
    assert animation.scene.workflow_phase == "idle"


def test_work_positions_are_continuous_across_phase_boundaries() -> None:
    animation = LabAnimation()
    base = _snapshot()
    animation.observe(base)
    animation.observe(replace(base, materials={"water": 1}))
    for _, duration in WORKFLOW:
        animation.advance(duration - 1)
        previous = animation.scene.character_position
        animation.advance(1)
        current = animation.scene.character_position
        assert all(abs(a - b) < 0.01 for a, b in zip(previous, current))


def test_each_material_arrives_and_leaves_basket_once_before_phase_ends() -> None:
    for count in range(1, 7):
        for index in range(count):
            for phase in ("arrive", "collect"):
                values = [material_transfer_progress(phase, step / 100, index, count) for step in range(101)]
                assert values[0] == 0
                assert values[-1] == 1
                assert values == sorted(values)
                assert 0 < values[50] < 1
            assert material_transfer_progress("collect", 0.28, index, count) == 0
            assert material_transfer_progress("collect", 0.95, index, count) == 1
