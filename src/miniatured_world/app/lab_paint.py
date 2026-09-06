"""独立したラボ素材の描画。背景と同じ1280x853舞台で合成する。"""

from importlib import resources
import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF

from miniatured_world.app.lab_layout import LabLayout
from miniatured_world.app.lab import LabScene, material_transfer_progress


def load_props() -> dict[str, QPixmap]:
    result = {}
    base = resources.files("miniatured_world") / "assets" / "props"
    for key, name in (("book", "lectern"), ("basket", "basket"), ("product", "tray")):
        image = QImage.fromData((base / f"{name}.png").read_bytes())
        if image.isNull() or not image.hasAlphaChannel():
            raise ValueError(f"透過素材を読み込めません: {name}")
        result[key] = QPixmap.fromImage(image)
    return result


def shadow(painter: QPainter, x: float, y: float, width: float, height: float = 12) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(36, 23, 37, 30))
    painter.drawEllipse(QRectF(x - width / 2, y - height / 2, width, height))


def draw_props(painter: QPainter, layout: LabLayout, props: dict[str, QPixmap]) -> None:
    for key in ("book", "basket", "product"):
        item = layout.gimmick(key)
        x, y = item.position
        width, height = item.size
        shadow(painter, x, y - 2, width * 0.8)
        painter.drawPixmap(QRectF(x - width / 2, y - height, width, height), props[key], QRectF(props[key].rect()))


def draw_character(painter: QPainter, layout: LabLayout, sprite: QPixmap, *, position=None) -> None:
    x, y = position or layout.character_home
    size = 128 * layout.pixel_scale
    shadow(painter, x, y - 2, size * 0.52)
    painter.drawPixmap(QRectF(x - size / 2, y - size * 120 / 128, size, size), sprite, QRectF(sprite.rect()))


def draw_cauldron(painter: QPainter, layout: LabLayout, sprite: QPixmap) -> None:
    item = layout.gimmick("cauldron")
    x, y = item.position
    width, height = item.size
    shadow(painter, x, y - 2, width * 0.65)
    painter.drawPixmap(QRectF(x - width / 2, y - height * 104 / 112, width, height), sprite, QRectF(sprite.rect()))


def _material(painter: QPainter, x: float, y: float, key: str, size: float = 8) -> None:
    colors = {"seed": "#98bc70", "water": "#83d8dd", "mineral": "#b0a0ee", "soil": "#b58a62", "sand": "#e5cc87", "food": "#e09d73"}
    painter.setPen(QPen(QColor("#4a3947"), 1))
    painter.setBrush(QColor(colors.get(key, "#b2d5a4")))
    painter.drawPolygon(QPolygonF([QPointF(x, y - size), QPointF(x + size * 0.6, y), QPointF(x, y + size * 0.6), QPointF(x - size * 0.6, y)]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#e8f1cb"))
    painter.drawRect(QRectF(x - 2, y - size + 3, 3, 3))


def _bottle(painter: QPainter, x: float, y: float) -> None:
    """完成品の小瓶。yは底面。輪郭と反射を持つ小さなピクセル形状。"""
    painter.setPen(QPen(QColor("#453a42"), 2))
    painter.setBrush(QColor("#bce5d7"))
    points = [(-4, -26), (4, -26), (4, -18), (10, -12), (10, -3), (6, 0), (-6, 0), (-10, -3), (-10, -12), (-4, -18)]
    painter.drawPolygon(QPolygonF([QPointF(x + a, y + b) for a, b in points]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#60bbaa"))
    painter.drawRect(QRectF(x - 7, y - 11, 14, 8))
    painter.setBrush(QColor("#e9f6e3"))
    painter.drawRect(QRectF(x - 6, y - 15, 3, 10))
    painter.setBrush(QColor("#c79a61"))
    painter.drawRect(QRectF(x - 4, y - 28, 8, 5))


def _prop(painter: QPainter, layout: LabLayout, props: dict[str, QPixmap], scene: LabScene, key: str) -> None:
    item = layout.gimmick(key)
    x, y = item.position
    width, height = item.size
    shadow(painter, x, y - 2, width * 0.8)
    painter.drawPixmap(QRectF(x - width / 2, y - height, width, height), props[key], QRectF(props[key].rect()))
    states = {value.placement.key: value.state for value in scene.gimmicks}
    if key == "book" and states[key] == "turning" and scene.phase_progress > 0.24:
        turn = ((scene.phase_progress - 0.24) / 0.76 * 2) % 1
        hinge_x, hinge_y = x, y - height + 31
        reach = 32 * math.cos(turn * math.pi)
        lift = 23 * math.sin(turn * math.pi)
        painter.setPen(QPen(QColor("#a88a59"), 1))
        painter.setBrush(QColor("#f0dfad"))
        painter.drawPolygon(QPolygonF([QPointF(hinge_x, hinge_y - 18), QPointF(hinge_x + reach, hinge_y - 13 - lift), QPointF(hinge_x + reach - 5, hinge_y + 12 - lift), QPointF(hinge_x - 7, hinge_y + 7)]))
    if key == "basket" and states[key] in {"arriving", "full", "taking"}:
        count = max(1, len(scene.batch_materials))
        for index, material in enumerate(scene.batch_materials):
            if states[key] == "arriving" and material_transfer_progress("arrive", scene.phase_progress, index, count) < 1:
                continue
            if states[key] == "taking" and material_transfer_progress("collect", scene.phase_progress, index, count) > 0:
                continue
            _material(painter, x - 22 + index * 9, y - 31, material)
        # 前側の縁だけを再描画して素材をかごの内部に見せる。
        sprite = props[key]
        painter.drawPixmap(QRectF(x - width / 2, y - height * 0.4, width, height * 0.4), sprite, QRectF(0, sprite.height() * 0.6, sprite.width(), sprite.height() * 0.4))
    if key == "product" and scene.product_visible and scene.workflow_phase != "place":
        _bottle(painter, x, y - 12)


def _draw_lab_scene(painter: QPainter, layout: LabLayout, props: dict[str, QPixmap], characters: dict[str, QPixmap], cauldrons: dict[str, tuple[QPixmap, ...]], scene: LabScene, elapsed_ms: int, frame_index: int) -> None:
    """接地位置の奥から順に描き、道具間の演出はその手前で描く。"""
    items = [(g.position[1], g.key) for g in layout.gimmicks]
    items.append((scene.character_position[1], "character"))
    for _, key in sorted(items):
        if key == "character":
            sprite = characters.get(scene.character_state) or characters["idle"]
            x, y = scene.character_position
            size = 128 * layout.pixel_scale
            shadow(painter, x, y - 2, size * 0.52)
            bob = -round(3 * abs(math.sin(elapsed_ms / 350))) if scene.character_state == "success" else 0
            painter.save()
            painter.translate(x, y + bob)
            if scene.facing_right:
                painter.scale(-1, 1)
            painter.drawPixmap(QRectF(-size / 2, -size * 120 / 128, size, size), sprite, QRectF(sprite.rect()))
            painter.restore()
        elif key == "cauldron":
            state = scene.cauldron_state.removeprefix("cauldron_")
            frames = cauldrons.get(state) or cauldrons["idle"]
            draw_cauldron(painter, layout, frames[frame_index % len(frames)])
        else:
            _prop(painter, layout, props, scene, key)

    phase, progress = scene.workflow_phase, scene.phase_progress
    bx, by = layout.gimmick("basket").position
    actor_x, actor_y = scene.character_position
    cauldron = layout.gimmick("cauldron")
    mouth_x = cauldron.position[0]
    mouth_y = cauldron.position[1] - cauldron.size[1] * 55 / 112
    if phase == "arrive":
        for index, material in enumerate(scene.batch_materials):
            t = material_transfer_progress(phase, progress, index, len(scene.batch_materials))
            if t < 1:
                target_x = bx - 22 + index * 9
                _material(painter, target_x - 170 * (1 - t), by - 31 - 170 * (1 - t) - 26 * math.sin(t * math.pi), material)
    elif phase == "collect":
        for index, material in enumerate(scene.batch_materials):
            t = material_transfer_progress(phase, progress, index, len(scene.batch_materials))
            if 0 < t < 1:
                source_x = bx - 22 + index * 9
                _material(painter, source_x + (actor_x - 44 - source_x) * t, by - 31 + (actor_y - 82 - by + 31) * t - 24 * math.sin(t * math.pi), material)
    elif phase == "mix" and progress > 0.18:
        for index in range(4):
            t = ((progress - 0.18) * 3 + index / 4) % 1
            x = actor_x - 82 + (mouth_x - actor_x + 82) * t
            y = actor_y - 124 + (mouth_y - actor_y + 124) * t - 12 * math.sin(t * math.pi)
            _material(painter, x, y, "water", 3)
    elif phase == "place":
        px, py = layout.gimmick("product").position
        t = min(1.0, max(0.0, (progress - 0.28) / 0.5))
        _bottle(painter, actor_x + 56 + (px - actor_x - 56) * t, actor_y - 154 + (py - 12 - actor_y + 154) * t)

    if "reaction_light" in scene.effects:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#b8f1be"))
        for index in range(4):
            angle = elapsed_ms / 750 + index * math.pi / 2
            x, y = mouth_x + math.cos(angle) * 43, mouth_y - 22 + math.sin(angle) * 13
            painter.drawRect(QRectF(x - 3, y - 1, 6, 2))
            painter.drawRect(QRectF(x - 1, y - 3, 2, 6))


def draw_lab_scene(painter: QPainter, layout: LabLayout, props: dict[str, QPixmap], characters: dict[str, QPixmap], cauldrons: dict[str, tuple[QPixmap, ...]], scene: LabScene, elapsed_ms: int, frame_index: int) -> None:
    """前景を共通の論理ピクセル面へ描き、整数倍で合成する。"""
    unit = layout.pixel_scale
    layer = QImage(math.ceil(1280 / unit), math.ceil(853 / unit), QImage.Format.Format_ARGB32_Premultiplied)
    layer.fill(Qt.GlobalColor.transparent)
    pixel_painter = QPainter(layer)
    pixel_painter.scale(1 / unit, 1 / unit)
    _draw_lab_scene(pixel_painter, layout, props, characters, cauldrons, scene, elapsed_ms, frame_index)
    pixel_painter.end()
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    painter.drawImage(QRectF(0, 0, layer.width() * unit, layer.height() * unit), layer)
    painter.restore()
