from miniatured_world.activity import ActivityFrame
from miniatured_world.world import WorldSession, WorldSimulation


def _run(seed: int) -> dict[str, object]:
    simulation = WorldSimulation(WorldSession.create(seed))
    frames = [
        ActivityFrame(0.9, 0.2, 0.1, 0.0, 0.7, 0.6, 0.2, 1.0),
        ActivityFrame(0.6, 0.6, 0.2, 0.2, 0.4, 0.8, 0.4, 2.0),
        ActivityFrame(0.2, 0.1, 0.0, 0.0, 0.1, 0.2, 0.9, 3.0),
        ActivityFrame(0.8, 0.4, 0.2, 0.1, 0.6, 0.6, 0.3, 4.0),
    ]
    for frame in frames:
        simulation.step(frame)
    return simulation.summary()


def test_world_replay_is_deterministic_for_same_seed_and_frames() -> None:
    assert _run(12345) == _run(12345)


def test_world_simulation_exercises_core_systems() -> None:
    summary = _run(777)

    assert summary["materials"]
    assert summary["grid_materials"]
    assert summary["creatures"]
    assert "environment" in summary

