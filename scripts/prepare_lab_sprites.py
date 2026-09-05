"""Crop the user-supplied 1280x853 reference sheets without resizing artwork."""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter


def transparent_crop(source: QImage, box: tuple[int, int, int, int]) -> QImage:
    x, y, width, height = box
    result = source.copy(x, y, width, height).convertToFormat(QImage.Format.Format_ARGB32)
    # Only remove light pixels connected to the crop boundary, preserving faces and clothes.
    queue = deque([(x, 0) for x in range(width)] + [(x, height - 1) for x in range(width)])
    queue.extend((x, y) for y in range(height) for x in (0, width - 1))
    visited: set[tuple[int, int]] = set()
    while queue:
        px, py = queue.popleft()
        if (px, py) in visited or not (0 <= px < width and 0 <= py < height):
            continue
        visited.add((px, py))
        color = result.pixelColor(px, py)
        channels = color.red(), color.green(), color.blue()
        if min(channels) < 202 or max(channels) - min(channels) > 42:
            continue
        result.setPixelColor(px, py, Qt.GlobalColor.transparent)
        queue.extend(((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)))
    return result


def place_on_canvas(crop: QImage, width: int, height: int, baseline: int) -> QImage:
    points = [(x, y) for y in range(crop.height()) for x in range(crop.width()) if crop.pixelColor(x, y).alpha()]
    left, right = min(x for x, _ in points), max(x for x, _ in points)
    top, bottom = min(y for _, y in points), max(y for _, y in points)
    art = crop.copy(left, top, right - left + 1, bottom - top + 1)
    if art.width() > width - 8 or art.height() > baseline - 4:
        raise ValueError("Crop exceeds the sprite safety margin")
    canvas = QImage(width, height, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawImage((width - art.width()) // 2, baseline - art.height(), art)
    painter.end()
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--characters", type=Path, required=True)
    parser.add_argument("--cauldron", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("src/miniatured_world/assets"))
    args = parser.parse_args()
    character = QImage(str(args.characters))
    cauldron = QImage(str(args.cauldron))
    for source in (character, cauldron):
        if source.size().toTuple() != (1280, 853):
            raise ValueError("Expected the approved 1280x853 reference sheet")
    character_boxes = {
        "idle": (16, 88, 148, 163),
        "work": (327, 300, 154, 160),
        "success": (488, 300, 151, 161),
        "failure": (641, 303, 153, 159),
        "rest": (2, 502, 161, 127),
    }
    target = args.output / "characters" / "alchemist_girl"
    target.mkdir(parents=True, exist_ok=True)
    for name, box in character_boxes.items():
        image = place_on_canvas(transparent_crop(character, box), 192, 192, 180)
        if not image.save(str(target / f"{name}.png")):
            raise OSError("Could not save character sprite")
    target = args.output / "cauldron" / "magic_cauldron"
    target.mkdir(parents=True, exist_ok=True)
    columns = (105, 191, 278, 366, 453, 541, 629, 717, 805)
    rows = {"idle": (55, 151), "receive": (176, 274), "failure": (297, 405), "success": (424, 531)}
    for state, (top, bottom) in rows.items():
        for index, (left, right) in enumerate(zip(columns, columns[1:]), 1):
            box = (left + 3, top, right - left - 6, bottom - top)
            image = place_on_canvas(transparent_crop(cauldron, box), 96, 128, 120)
            if not image.save(str(target / f"{state}_{index:02d}.png")):
                raise OSError("Could not save cauldron sprite")
    manifest = {
        "character_source_sha256": hashlib.sha256(args.characters.read_bytes()).hexdigest(),
        "cauldron_source_sha256": hashlib.sha256(args.cauldron.read_bytes()).hexdigest(),
        "character_boxes_xywh": character_boxes,
        "cauldron_columns": columns,
        "cauldron_rows_y": rows,
        "character_canvas": [192, 192],
        "character_baseline": 180,
        "cauldron_canvas": [96, 128],
        "cauldron_baseline": 120,
    }
    (args.output / "sprites_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
