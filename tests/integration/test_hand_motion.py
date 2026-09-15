"""連続原画の接触・合成・停止を実際のQt描画で検査する。"""
import hashlib
import json
import math
import os
from dataclasses import replace
from importlib import resources

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.hand_motion import motion_clip, motion_data
from miniatured_world.app.lab_hands import grip_position, page_corner, vessel_opening
from miniatured_world.app.lab_layout import DEFAULT_LAYOUT
from miniatured_world.app.lab_paint import draw_lab_scene
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


@pytest.fixture
def lab():
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=17, provider=DemoActivityProvider())
    window = build_main_window(runtime)
    window.timer.stop()
    preview = window.world_tab.preview
    original = runtime.snapshot()
    base = replace(original, materials={}, events=(), discoveries=())

    def start():
        preview.set_snapshot(replace(base, seed=18))
        preview.set_snapshot(base)
        delivered = replace(base, materials=dict.fromkeys(("seed", "water", "soil", "sand", "mineral", "food"), 1), world_time=2)
        preview.set_snapshot(delivered)
        return delivered

    yield app, runtime, window, preview, start
    assert runtime.snapshot() == original
    preview.close()
    window.shutdown()
    runtime.stop()


def _at(preview, action, index):
    target = preview.animation.action_start_ms(action) + motion_clip(action).frame_start(index)
    preview.animation.advance(target - preview.animation.elapsed_ms)
    return preview.animation.scene


def test_contacts_reach_the_actual_gimmick_regions_and_release_page(lab):
    _, _, _, preview, start = lab
    start()
    for index in range(4, 8):
        scene = _at(preview, "read", index)
        x, y = grip_position(scene, DEFAULT_LAYOUT)
        assert 816 <= x <= 880 and 562 <= y <= 596
        assert page_corner(scene, DEFAULT_LAYOUT) == (x, y)
    released = _at(preview, "read", 8)
    assert page_corner(released, DEFAULT_LAYOUT) != grip_position(released, DEFAULT_LAYOUT)
    preview.animation.advance(300)
    assert page_corner(preview.animation.scene, DEFAULT_LAYOUT) is None
    for index in (7, 8):
        scene = _at(preview, "collect", index)
        assert math.dist(grip_position(scene, DEFAULT_LAYOUT), (660, 736)) / 2 <= 2
    for index in (11, 12):
        scene = _at(preview, "mix", index)
        x, y = vessel_opening(scene, DEFAULT_LAYOUT)
        assert ((x - 510) / 55) ** 2 + ((y - 620) / 17) ** 2 <= 1
    for index in (7, 8):
        scene = _at(preview, "place", index)
        assert math.dist(grip_position(scene, DEFAULT_LAYOUT), (788, 718)) / 2 <= 2
    assert preview.animation.scene.vessel_location == "tray"
    assert 718 + (motion_data()["vial"]["base"][1] - motion_data()["vial"]["grip"][1]) * 2 == 746


def test_production_art_has_44_originals_and_masks_preserve_pixels():
    root = resources.files("miniatured_world") / "assets"
    data = json.loads((root / "hand_motion.json").read_text())
    originals = set()
    for action, clip in data["series"].items():
        assert 8 <= len(clip["frames"]) <= 16
        for frame in clip["frames"]:
            image = QImage.fromData((root / frame["sprite"]).read_bytes()).convertToFormat(QImage.Format.Format_RGBA8888)
            mask = QImage.fromData((root / frame["hand_mask"]).read_bytes()).convertToFormat(QImage.Format.Format_RGBA8888)
            pixels, hands = bytes(image.constBits()), bytes(mask.constBits())
            originals.add(hashlib.sha256(pixels).hexdigest())
            assert all(hands[i:i + 4] == pixels[i:i + 4] for i in range(0, len(hands), 4) if hands[i + 3])
            for point in ("grip", "left_wrist", "right_wrist"):
                assert image.pixelColor(*frame[point]).alpha() == 255
            for x, y in frame["feet"]:
                assert image.pixelColor(x, y - 1).alpha() or image.pixelColor(x, y - 2).alpha()
        for a, b in zip(clip["frames"], clip["frames"][1:]):
            for point in ("grip", "left_wrist", "right_wrist"):
                assert math.dist(a[point], b[point]) <= 8, (action, point)
    assert len(originals) >= 44
    # 歩行と取得終端は同じ手を使い、瓶を別レイヤーにしたまま運ぶ。
    last = data["series"]["collect"]["frames"][-1]
    for frame in data["walking"]:
        assert frame["grip"] == last["grip"]
        image = QImage.fromData((root / frame["sprite"]).read_bytes()).convertToFormat(QImage.Format.Format_RGBA8888)
        mask = QImage.fromData((root / frame["hand_mask"]).read_bytes()).convertToFormat(QImage.Format.Format_RGBA8888)
        pixels, hands = bytes(image.constBits()), bytes(mask.constBits())
        assert all(hands[i:i + 4] == pixels[i:i + 4] for i in range(0, len(hands), 4) if hands[i + 3])


def test_every_hand_frame_keeps_the_shared_pixel_grid(lab):
    _, _, _, preview, start = lab
    start()
    for action in ("read", "collect", "mix", "place"):
        for index in range(len(motion_clip(action).frames)):
            scene = _at(preview, action, index)
            image = QImage(1280, 854, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            draw_lab_scene(painter, DEFAULT_LAYOUT, preview._props, preview._character_sprites, preview._cauldron_sprites, scene, preview.animation.elapsed_ms, preview.animation.frame_index, hand_assets=preview._hand_assets)
            painter.end()
            restored = image.scaled(640, 427, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation).scaled(1280, 854, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            assert bytes(image.constBits()) == bytes(restored.constBits()), (action, index)


@pytest.mark.parametrize("size", ((640, 427), (900, 620), (1280, 720)))
def test_contact_poses_render_at_three_viewport_sizes(lab, size):
    _, _, _, preview, start = lab
    preview.setParent(None)
    preview.resize(*size)
    start()
    rendered = set()
    for action, index in (("read", 5), ("collect", 8), ("mix", 12), ("place", 8)):
        _at(preview, action, index)
        image = QImage(*size, QImage.Format.Format_RGB32)
        preview.render(image)
        rendered.add(bytes(image.constBits()))
    assert len(rendered) == 4


def test_tab_hide_and_pause_freeze_contact_pixels_and_resume(lab):
    app, _, window, preview, start = lab
    window.show()
    app.processEvents()
    delivered = start()
    _at(preview, "collect", 8)
    before = preview.animation.scene
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    QTest.qWait(100)
    assert not preview.animation_timer.isActive()
    assert preview.animation.scene == before
    window.tabs.setCurrentIndex(0)
    window.refresh(replace(delivered, paused=True))
    before = preview.animation.scene
    image = QImage(preview.size(), QImage.Format.Format_RGB32)
    preview.render(image)
    QTest.qWait(100)
    frozen = QImage(preview.size(), QImage.Format.Format_RGB32)
    preview.render(frozen)
    assert image == frozen
    assert preview.animation.scene == before
    window.refresh(delivered)
    QTest.qWait(100)
    assert preview.animation.elapsed_ms > before.transfers[-1].elapsed_ms
    assert [event.kind for event in preview.animation.scene.transfers].count("collect") == 1
