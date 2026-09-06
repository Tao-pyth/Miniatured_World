"""アプリ自身の素材だけで静止構図3案を描画する。"""

import os
from pathlib import Path
from dataclasses import replace
import subprocess
from importlib import resources

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from miniatured_world.app.lab_layout import LabLayout
from miniatured_world.app.lab_paint import draw_lab_scene, load_props
from miniatured_world.app.lab import LabAnimation
from miniatured_world.app.runtime import AppRuntime
from miniatured_world.activity import DemoActivityProvider


def main() -> None:
    app = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont("C:/Windows/Fonts/YuGothR.ttc")
    family = QFontDatabase.applicationFontFamilies(font_id)[0]
    base = resources.files("miniatured_world") / "assets"
    background = QPixmap.fromImage(QImage.fromData((base / "little_laboratory_background.png").read_bytes()))
    characters = {state: QPixmap.fromImage(QImage.fromData((base / f"characters/alchemist_girl/{state}.png").read_bytes())) for state in ("idle", "work", "success", "failure", "rest")}
    cauldrons = {"idle": tuple(QPixmap.fromImage(QImage.fromData((base / f"cauldron/magic_cauldron/idle_{index:02}.png").read_bytes())) for index in range(1, 9))}
    runtime = AppRuntime.start(seed=17, provider=DemoActivityProvider())
    props = load_props()
    output = Path("logs/pixel-v0.9.3/comparison")
    output.mkdir(parents=True, exist_ok=True)
    contact = QImage(1280 * 3, 913, QImage.Format.Format_RGB32)
    contact.fill(QColor("#24242a"))
    contact_painter = QPainter(contact)
    contact_painter.setFont(QFont(family, 23))
    contact_painter.setPen(QColor("#fff0d4"))
    for index, (name, unit, label) in enumerate((
        ("a-original", 0, "A v0.9.2 素材ごとに異なる倍率"),
        ("b-two", 2, "B 全前景を共通2倍 / 採用候補"),
        ("c-three", 3, "C 全前景を共通3倍 / 大きさ比較"),
    )):
        image = QImage(1280, 853, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        painter.drawPixmap(QRectF(0, 0, 1280, 853), background, QRectF(background.rect()))
        if unit == 0:
            original = QImage.fromData(subprocess.check_output(["git", "show", "v0.9.2:docs/images/lab-preview.png"]))
            painter.drawImage(0, 0, original)
        else:
            layout = LabLayout(pixel_scale=unit)
            animation = LabAnimation(layout)
            animation.observe(replace(runtime.snapshot(), materials={}, discoveries=(), events=(), activity_level="calm", activity_intensity=0))
            draw_lab_scene(painter, layout, props, characters, cauldrons, animation.scene, 0, 0)
        painter.end()
        image.save(str(output / f"{name}.png"))
        contact_painter.drawText(index * 1280 + 24, 42, label)
        contact_painter.drawImage(index * 1280, 60, image)
    contact_painter.end()
    contact.save(str(output / "comparison.png"))
    runtime.stop()
    print(output / "comparison.png")


if __name__ == "__main__":
    main()
