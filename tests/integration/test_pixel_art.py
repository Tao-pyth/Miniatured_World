"""素材の密度差と、拡縮によるドットの崩れを防ぐ回帰検査。"""

import json
import hashlib
from dataclasses import replace
from importlib import resources

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.lab import WORKFLOW
from miniatured_world.app.lab_layout import DEFAULT_LAYOUT
from miniatured_world.app.lab_paint import draw_lab_scene
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def test_all_foreground_assets_share_palette_and_binary_alpha() -> None:
    root = resources.files("miniatured_world") / "assets"
    manifest = json.loads((root / "sprites_manifest.json").read_text())
    palette = {tuple(color) for color in manifest["palette"]}
    assert len(palette) <= 64
    assert len(manifest["files"]) == 40
    for record in manifest["files"]:
        data = (root / record["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record["sha256"]
        image = QImage.fromData(data).convertToFormat(QImage.Format.Format_RGBA8888)
        assert image.size().toTuple() == tuple(record["size"])
        pixels = bytes(image.constBits())
        assert set(pixels[3::4]) == {0, 255}
        assert all(tuple(pixels[i:i + 3]) in palette for i in range(0, len(pixels), 4) if pixels[i + 3])
    stable_bodies = set()
    for state in ("idle", "receive", "failure", "success"):
        for index in range(1, 9):
            image = QImage.fromData((root / f"cauldron/magic_cauldron/{state}_{index:02}.png").read_bytes())
            body = image.copy(0, 48, 96, 64)
            stable_bodies.add(bytes(body.constBits()))
    assert len(stable_bodies) == 1
    for prop, name in (("book", "lectern"), ("basket", "basket"), ("product", "tray")):
        image = QImage.fromData((root / f"props/{name}.png").read_bytes())
        assert DEFAULT_LAYOUT.gimmick(prop).size == (image.width() * 2, image.height() * 2)


def test_every_workflow_stage_keeps_a_common_two_pixel_grid() -> None:
    app = QApplication.instance() or QApplication([])
    runtime = AppRuntime.start(seed=17, provider=DemoActivityProvider())
    window = build_main_window(runtime)
    window.timer.stop()
    preview = window.world_tab.preview
    base = replace(runtime.snapshot(), materials={}, events=(), discoveries=())
    preview.set_snapshot(replace(base, seed=18))
    preview.set_snapshot(base)
    preview.set_snapshot(replace(base, materials={"seed": 2}))
    try:
        for phase, duration in WORKFLOW:
            preview.animation.advance(duration // 2)
            image = QImage(1280, 854, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            draw_lab_scene(painter, DEFAULT_LAYOUT, preview._props, preview._character_sprites, preview._cauldron_sprites, preview.animation.scene, preview.animation.elapsed_ms, preview.animation.frame_index)
            painter.end()
            # 2x2を一つの論理ピクセルへ戻し再拡大しても完全一致する。
            restored = image.scaled(640, 427, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation).scaled(1280, 854, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            assert bytes(image.constBits()) == bytes(restored.constBits()), phase
            preview.animation.advance(duration - duration // 2)
    finally:
        window.close()
        runtime.stop()
