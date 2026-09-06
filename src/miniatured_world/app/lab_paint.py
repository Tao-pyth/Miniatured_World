"""独立したラボ素材の描画。背景と同じ1280x853舞台で合成する。"""

from importlib import resources
import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF

from miniatured_world.app.lab_layout import LabLayout
from miniatured_world.app.lab import LabScene, material_transfer_progress
from miniatured_world.app.hand_motion import motion_clip
from miniatured_world.app.lab_hands import MATERIAL_COLORS, draw_hand_overlays, load_hand_assets, scene_pose, vessel_opening


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
    painter.setPen(QPen(QColor("#4a3947"), 1))
    painter.setBrush(QColor(MATERIAL_COLORS.get(key, "#b2d5a4")))
    painter.drawPolygon(QPolygonF([QPointF(x, y - size), QPointF(x + size * 0.6, y), QPointF(x, y + size * 0.6), QPointF(x - size * 0.6, y)]))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#e8f1cb"))
    painter.drawRect(QRectF(x - 2, y - size + 3, 3, 3))


def _prop(painter: QPainter, layout: LabLayout, props: dict[str, QPixmap], key: str) -> None:
    item = layout.gimmick(key)
    x, y = item.position
    width, height = item.size
    shadow(painter, x, y - 2, width * 0.8)
    painter.drawPixmap(QRectF(x - width / 2, y - height, width, height), props[key], QRectF(props[key].rect()))


def _draw_lab_scene(painter: QPainter, layout: LabLayout, props: dict[str, QPixmap], characters: dict[str, QPixmap], cauldrons: dict[str, tuple[QPixmap, ...]], scene: LabScene, elapsed_ms: int, frame_index: int, hand_assets: dict[str, QPixmap]) -> None:
    """接地位置の奥から順に描き、道具間の演出はその手前で描く。"""
    items = [(g.position[1], g.key) for g in layout.gimmicks]
    items.append((scene.character_position[1], "character"))
    state = scene.cauldron_state.removeprefix("cauldron_")
    frames = cauldrons.get(state) or cauldrons["idle"]
    pot = frames[frame_index % len(frames)]
    for _, key in sorted(items):
        if key == "character":
            pose = scene_pose(scene)
            sprite_key = pose.sprite.rsplit("/", 1)[-1].removesuffix(".png") if pose else scene.character_state
            if pose is None and sprite_key in {"idle", "work", "rest"}:
                sprite_key = "collect_01"
            sprite = characters.get(sprite_key) or characters["idle"]
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
            draw_cauldron(painter, layout, pot)
        else:
            _prop(painter, layout, props, key)

    draw_hand_overlays(painter, layout, props, pot, scene, hand_assets)

    if scene.walk_frame is not None:
        return
    phase, progress = scene.workflow_phase, scene.action_progress
    bx, by = layout.gimmick("basket").position
    actor_x, actor_y = scene.character_position
    cauldron = layout.gimmick("cauldron")
    mouth_x = cauldron.position[0]
    mouth_y = cauldron.position[1] - cauldron.size[1] * 55 / 112
    if phase == "arrive":
        for index, material in enumerate(scene.batch_materials):
            t = material_transfer_progress(phase, progress, index, len(scene.batch_materials))
            if t < 1:
                _material(painter, bx - 170 * (1 - t), by - 34 - 170 * (1 - t) - 26 * math.sin(t * math.pi), material, 4)
    elif phase == "mix" and scene.action_frame is not None:
        clip = motion_clip("mix")
        if clip.event_frame("pour_start") <= scene.action_frame < clip.event_frame("pour_end"):
            opening = vessel_opening(scene, layout)
            if opening is not None:
                painter.setPen(QPen(QColor("#83d8dd"), layout.pixel_scale))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPolyline(QPolygonF([QPointF(*opening), QPointF((opening[0] + mouth_x) / 2, opening[1] + 8), QPointF(mouth_x, mouth_y)]))

    if "reaction_light" in scene.effects:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#b8f1be"))
        for index in range(4):
            angle = elapsed_ms / 750 + index * math.pi / 2
            x, y = mouth_x + math.cos(angle) * 43, mouth_y - 22 + math.sin(angle) * 13
            painter.drawRect(QRectF(x - 3, y - 1, 6, 2))
            painter.drawRect(QRectF(x - 1, y - 3, 2, 6))


def draw_lab_scene(painter: QPainter, layout: LabLayout, props: dict[str, QPixmap], characters: dict[str, QPixmap], cauldrons: dict[str, tuple[QPixmap, ...]], scene: LabScene, elapsed_ms: int, frame_index: int, *, hand_assets: dict[str, QPixmap] | None = None) -> None:
    """前景を共通の論理ピクセル面へ描き、整数倍で合成する。"""
    unit = layout.pixel_scale
    layer = QImage(math.ceil(1280 / unit), math.ceil(853 / unit), QImage.Format.Format_ARGB32_Premultiplied)
    layer.fill(Qt.GlobalColor.transparent)
    pixel_painter = QPainter(layer)
    pixel_painter.scale(1 / unit, 1 / unit)
    _draw_lab_scene(pixel_painter, layout, props, characters, cauldrons, scene, elapsed_ms, frame_index, hand_assets if hand_assets is not None else load_hand_assets())
    pixel_painter.end()
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    painter.drawImage(QRectF(0, 0, layer.width() * unit, layer.height() * unit), layer)
    painter.restore()
