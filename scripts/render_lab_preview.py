"""Render only the app's synthetic lab scene, never the user's desktop."""

from __future__ import annotations

import argparse
from dataclasses import replace
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("logs/lab-visual-quality"))
    parser.add_argument("--gif", type=Path, help="Optional GIF output; requires Pillow for encoding")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    font_path = Path("C:/Windows/Fonts/YuGothR.ttc")
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0]))
    runtime = AppRuntime.start(seed=20260825, provider=DemoActivityProvider())
    window = build_main_window(runtime)
    window.timer.stop()
    preview = window.world_tab.preview
    base = replace(runtime.snapshot(), activity_level="calm", activity_intensity=0, materials={}, grid_materials={}, events=(), discoveries=())
    states = {
        "idle": base,
        "work": replace(base, activity_level="active", activity_intensity=0.6, materials={"seed": 2, "water": 1, "mineral": 1}),
        "success": replace(base, activity_level="active", activity_intensity=0.6, materials={"seed": 2}, discoveries=("new",)),
        "failure": replace(base, activity_level="intense", activity_intensity=0.9),
        "rest": replace(base, activity_level="quiet"),
    }
    try:
        window.resize(1100, 940)
        window.show()
        app.processEvents()
        window.refresh(states["work"])
        preview.animation_timer.stop()
        window_image = QImage(window.size(), QImage.Format.Format_RGB32)
        window.render(window_image)
        window_image.save(str(args.output / "window.png"))
        window.hide()
        preview.setParent(None)
        # Direct QWidget rendering works without capturing other windows or live input.
        for name, snapshot in states.items():
            preview.set_snapshot(replace(base, seed=base.seed + 1))
            preview.set_snapshot(base)
            preview.set_snapshot(snapshot)
            preview.resize(1280, 853)
            image = QImage(1280, 853, QImage.Format.Format_RGB32)
            image.fill(QColor("black"))
            preview.render(image)
            image.save(str(args.output / f"{name}.png"))
        preview.set_snapshot(base)
        preview.set_snapshot(states["work"])
        for width, height in ((640, 427), (1280, 720), (900, 620)):
            preview.resize(width, height)
            image = QImage(width, height, QImage.Format.Format_RGB32)
            preview.render(image)
            image.save(str(args.output / f"layout-{width}x{height}.png"))
        preview.resize(960, 640)
        for index in range(64):
            if index == 24:
                preview.set_snapshot(states["success"])
            if index == 52:
                preview.set_snapshot(states["work"])
            frame = QImage(960, 640, QImage.Format.Format_RGB32)
            preview.render(frame)
            frame.save(str(args.output / f"frame-{index:03d}.png"))
            preview.animation.advance(125)
        contact = QImage(960, 640, QImage.Format.Format_RGB32)
        contact.fill(QColor("#29282d"))
        painter = QPainter(contact)
        for index, name in enumerate(states):
            painter.drawImage(index % 3 * 320, index // 3 * 320 + 24, QImage(str(args.output / f"{name}.png")).scaled(320, 214))
            painter.setPen(QColor("white"))
            painter.drawText(index % 3 * 320 + 12, index // 3 * 320 + 20, name)
        painter.end()
        contact.save(str(args.output / "states.png"))
        if args.gif:
            from PIL import Image

            frames = [Image.open(args.output / f"frame-{index:03d}.png").convert("RGB") for index in range(64)]
            sample = Image.new("RGB", (960, 1280))
            sample.paste(frames[0], (0, 0))
            sample.paste(frames[24], (0, 640))
            palette = sample.quantize(colors=256)
            frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
            args.gif.parent.mkdir(parents=True, exist_ok=True)
            frames[0].save(args.gif, save_all=True, append_images=frames[1:], duration=[120, 130] * 32, loop=0, optimize=True)
    finally:
        preview.close()
        window.close()
        runtime.stop()


if __name__ == "__main__":
    main()
