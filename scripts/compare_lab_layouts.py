"""アプリ自身の素材だけで静止構図3案を描画する。"""

import os
from pathlib import Path
from importlib import resources

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from miniatured_world.app.lab_layout import LabLayout
from miniatured_world.app.lab_paint import draw_cauldron, draw_character, draw_props, load_props


def main() -> None:
    app = QApplication.instance() or QApplication([])
    font_id = QFontDatabase.addApplicationFont("C:/Windows/Fonts/YuGothR.ttc")
    family = QFontDatabase.applicationFontFamilies(font_id)[0]
    base = resources.files("miniatured_world") / "assets"
    background = QPixmap.fromImage(QImage.fromData((base / "little_laboratory_background.png").read_bytes()))
    character = QPixmap.fromImage(QImage.fromData((base / "characters/alchemist_girl/work.png").read_bytes()))
    cauldron = QPixmap.fromImage(QImage.fromData((base / "cauldron/magic_cauldron/receive_01.png").read_bytes()))
    props = load_props()
    output = Path("logs/lab-workspace/comparison")
    output.mkdir(parents=True, exist_ok=True)
    contact = QImage(1280 * 3, 913, QImage.Format.Format_RGB32)
    contact.fill(QColor("#24242a"))
    contact_painter = QPainter(contact)
    contact_painter.setFont(QFont(family, 23))
    contact_painter.setPen(QColor("#fff0d4"))
    for index, (name, scales, label) in enumerate((
        ("a-current", (1.0, 1.0), "A 現倍率  人物1.0 / 釜1.0"),
        ("b-middle", (1.2, 1.15), "B 中間案  人物1.2 / 釜1.15"),
        ("c-large", (1.4, 1.3), "C 比較案  人物1.4 / 釜1.3"),
    )):
        layout = LabLayout(*scales)
        image = QImage(1280, 853, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        painter.drawPixmap(QRectF(0, 0, 1280, 853), background, QRectF(background.rect()))
        draw_props(painter, layout, props)
        draw_cauldron(painter, layout, cauldron)
        draw_character(painter, layout, character)
        painter.end()
        image.save(str(output / f"{name}.png"))
        contact_painter.drawText(index * 1280 + 24, 42, label)
        contact_painter.drawImage(index * 1280, 60, image)
    contact_painter.end()
    contact.save(str(output / "comparison.png"))
    print(output / "comparison.png")


if __name__ == "__main__":
    main()
