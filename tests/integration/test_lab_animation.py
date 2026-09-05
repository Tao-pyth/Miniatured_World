import os
from dataclasses import replace
from importlib import resources

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def test_real_animation_timer_runs_without_ticking_simulation_and_stops_when_hidden() -> None:
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=17, provider=DemoActivityProvider())
    window = build_main_window(runtime)
    window.timer.stop()
    window.show()
    app.processEvents()
    preview = window.world_tab.preview
    before = runtime.snapshot()
    try:
        first = preview.grab().toImage()
        QTest.qWait(180)
        assert preview.animation.elapsed_ms >= 125
        assert first != preview.grab().toImage()
        assert runtime.snapshot() == before
        assert preview.animation_timer.isActive()

        window.tabs.setCurrentIndex(1)
        app.processEvents()
        assert not preview.animation_timer.isActive()
        frozen = preview.animation.elapsed_ms
        QTest.qWait(100)
        assert preview.animation.elapsed_ms == frozen
        window.tabs.setCurrentIndex(0)
        app.processEvents()
        assert preview.animation_timer.isActive()

        window.refresh(replace(before, paused=True))
        assert not preview.animation_timer.isActive()
        window.refresh(before)
        assert preview.animation_timer.isActive()
        window.refresh(replace(before, world_visible=False))
        assert not preview.animation_timer.isActive()
        window.refresh(before)
        assert preview.animation_timer.isActive()
    finally:
        window.close()
        runtime.stop()
    assert not preview.animation_timer.isActive()
    assert not window.timer.isActive()


def test_sprite_assets_have_safe_borders_consistent_baselines_and_eight_distinct_frames() -> None:
    base = resources.files("miniatured_world") / "assets"
    for folder, states, size, baseline, count in (
        ("characters/alchemist_girl", ("idle", "work", "success", "failure", "rest"), (192, 192), 180, 1),
        ("cauldron/magic_cauldron", ("idle", "receive", "success", "failure"), (96, 128), 120, 8),
    ):
        for state in states:
            contents = set()
            for index in range(1, count + 1):
                name = f"{state}.png" if count == 1 else f"{state}_{index:02d}.png"
                data = (base / folder / name).read_bytes()
                image = QImage.fromData(data)
                assert image.size().toTuple() == size
                assert image.hasAlphaChannel()
                points = [(x, y) for y in range(size[1]) for x in range(size[0]) if image.pixelColor(x, y).alpha()]
                assert min(x for x, _ in points) >= 4
                assert max(x for x, _ in points) < size[0] - 4
                assert min(y for _, y in points) >= 4
                assert max(y for _, y in points) == baseline - 1
                contents.add(bytes(image.constBits()))
            assert len(contents) == count


def test_all_cauldron_frames_change_rendered_pixels_at_multiple_sizes() -> None:
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=17, provider=DemoActivityProvider())
    window = build_main_window(runtime)
    window.timer.stop()
    preview = window.world_tab.preview
    preview.setParent(None)
    try:
        snapshot = runtime.snapshot()
        for size in ((640, 427), (1280, 720), (900, 620)):
            preview.resize(*size)
            for activity, intensity, materials, discoveries in (
                ("quiet", 0, {}, ()),
                ("active", 0.5, {"seed": 2}, ()),
                ("intense", 0.9, {}, ()),
                ("active", 0.5, {"seed": 2}, ("new",)),
            ):
                preview.set_snapshot(replace(snapshot, seed=18))
                preview.set_snapshot(snapshot)
                preview.set_snapshot(replace(snapshot, activity_level=activity, activity_intensity=intensity, materials=materials, discoveries=discoveries))
                frames = set()
                for _ in range(8):
                    image = QImage(*size, QImage.Format.Format_RGB32)
                    preview.render(image)
                    assert preview.size().toTuple() == size
                    assert image.pixelColor(size[0] // 2, size[1] // 2).alpha() == 255
                    frames.add(bytes(image.constBits()))
                    preview.animation.advance(125)
                assert len(frames) == 8
    finally:
        preview.close()
        window.close()
        runtime.stop()
