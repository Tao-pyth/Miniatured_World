"""サニタイズ済みデモ状態から実描画の作業連携を保存する。"""

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication

from miniatured_world.activity import DemoActivityProvider
from miniatured_world.app.qt_widgets import build_main_window
from miniatured_world.app.runtime import AppRuntime


def main() -> None:
    app = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont("C:/Windows/Fonts/YuGothR.ttc")
    family = QFontDatabase.applicationFontFamilies(font_id)[0]
    runtime = AppRuntime.start(seed=17, provider=DemoActivityProvider())
    window = build_main_window(runtime)
    window.timer.stop()
    preview = window.world_tab.preview
    preview.setParent(None)
    preview.resize(1280, 853)
    output = Path("logs/lab-workspace/workflow")
    output.mkdir(parents=True, exist_ok=True)
    base = replace(runtime.snapshot(), materials={}, grid_materials={}, discoveries=(), events=(), activity_level="calm", activity_intensity=0)
    preview.set_snapshot(replace(base, seed=18))
    preview.set_snapshot(base)
    delivered = replace(base, world_time=2, materials={"seed": 2, "water": 1, "mineral": 1}, activity_level="active", activity_intensity=0.5)
    preview.set_snapshot(delivered)
    frames = []
    captured = set()
    try:
        for index in range(104):
            image = QImage(1280, 853, QImage.Format.Format_RGB32)
            preview.render(image)
            scene = preview.animation.scene
            if scene.phase_progress >= 0.5 and scene.workflow_phase not in captured:
                image.save(str(output / f"{scene.workflow_phase}.png"))
                captured.add(scene.workflow_phase)
            canvas = QImage(960, 678, QImage.Format.Format_RGB32)
            canvas.fill(QColor("#29282d"))
            painter = QPainter(canvas)
            painter.drawImage(0, 0, image.scaled(960, 640))
            painter.setFont(QFont(family, 14))
            painter.setPen(QColor("#f4e8d2"))
            painter.drawText(24, 666, scene.caption)
            painter.end()
            path = output / f"frame-{index:03}.png"
            canvas.save(str(path))
            frames.append(path)
            preview.animation.advance(125)
        from PIL import Image

        images = [Image.open(path).convert("RGB") for path in frames]
        sample = Image.new("RGB", (960, 678 * 3))
        for row, index in enumerate((0, 48, 76)):
            sample.paste(images[index], (0, row * 678))
        palette = sample.quantize(colors=256)
        images = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
        images[0].save(output / "workflow.gif", save_all=True, append_images=images[1:], duration=[120, 130] * 52, loop=0)
        print(output / "workflow.gif")
    finally:
        preview.close()
        window.close()
        runtime.stop()


if __name__ == "__main__":
    main()
