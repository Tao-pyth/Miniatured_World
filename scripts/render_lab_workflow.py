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
from miniatured_world.app.lab import CYCLE_MS


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
    output = Path("logs/hand-motion-v0.9.5/workflow")
    output.mkdir(parents=True, exist_ok=True)
    (output / "poses").mkdir(exist_ok=True)
    base = replace(runtime.snapshot(), materials={}, grid_materials={}, discoveries=(), events=(), activity_level="calm", activity_intensity=0)
    preview.set_snapshot(replace(base, seed=18))
    preview.set_snapshot(base)
    delivered = replace(base, world_time=2, materials={"seed": 2, "water": 1, "mineral": 1}, activity_level="active", activity_intensity=0.5)
    preview.set_snapshot(delivered)
    frames = []
    captured = set()
    try:
        for index in range((CYCLE_MS + 1200) // 50 + 1):
            image = QImage(1280, 854, QImage.Format.Format_RGB32)
            image.fill(QColor("#29282d"))
            preview.render(image)
            scene = preview.animation.scene
            if scene.action_frame is not None:
                pose_key = f"{scene.workflow_phase}-{scene.action_frame + 1:02}"
                if pose_key not in captured:
                    image.save(str(output / "poses" / f"{pose_key}.png"))
                    captured.add(pose_key)
            for event in scene.transfers:
                event_key = f"event-{event.kind}"
                if event_key not in captured:
                    image.save(str(output / f"{event_key}.png"))
                    captured.add(event_key)
            walk_key = f"walk-{scene.workflow_phase}"
            if scene.walk_frame == 2 and walk_key not in captured:
                image.save(str(output / f"{walk_key}.png"))
                captured.add(walk_key)
            if scene.phase_progress >= 0.5 and scene.workflow_phase not in captured:
                image.save(str(output / f"{scene.workflow_phase}.png"))
                captured.add(scene.workflow_phase)
            canvas = QImage(640, 458, QImage.Format.Format_RGB32)
            canvas.fill(QColor("#29282d"))
            painter = QPainter(canvas)
            painter.drawImage(0, 0, image.scaled(640, 427))
            painter.setFont(QFont(family, 12))
            painter.setPen(QColor("#f4e8d2"))
            painter.drawText(16, 448, scene.caption)
            painter.end()
            path = output / f"frame-{index:03}.png"
            canvas.save(str(path))
            frames.append(path)
            preview.animation.advance(50)
        from PIL import Image

        images = [Image.open(path).convert("RGB") for path in frames]
        sample = Image.new("RGB", (640, 458 * 3))
        for row, index in enumerate((0, 120, 190)):
            sample.paste(images[index], (0, row * 458))
        palette = sample.quantize(colors=256)
        images = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
        images[0].save(output / "workflow.gif", save_all=True, append_images=images[1:], duration=50, loop=0)
        images[0].save(output / "workflow-slow.gif", save_all=True, append_images=images[1:], duration=100, loop=0)
        for action in ("read", "collect", "mix", "place"):
            paths = sorted((output / "poses").glob(f"{action}-*.png"))
            close = [Image.open(path).convert("RGB").crop((430, 440, 970, 790)).resize((810, 525), Image.Resampling.NEAREST) for path in paths]
            close_palette = close[len(close) // 2].quantize(colors=256)
            close = [frame.quantize(palette=close_palette, dither=Image.Dither.NONE) for frame in close]
            from miniatured_world.app.hand_motion import motion_clip
            durations = [frame.duration_ms for frame in motion_clip(action).frames]
            close[0].save(output / f"{action}-close.gif", save_all=True, append_images=close[1:], duration=durations, loop=0)
            close[0].save(output / f"{action}-close-slow.gif", save_all=True, append_images=close[1:], duration=[duration * 2 for duration in durations], loop=0)
        print(output / "workflow.gif")
    finally:
        preview.close()
        window.close()
        runtime.stop()


if __name__ == "__main__":
    main()
