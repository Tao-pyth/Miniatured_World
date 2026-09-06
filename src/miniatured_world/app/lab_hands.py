"""原画の接点へ道具を接続し、指・ページ・容器・前縁を合成する。"""
from __future__ import annotations

from importlib import resources
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF

from miniatured_world.app.hand_motion import MotionFrame, motion_clip, motion_data
from miniatured_world.app.lab import LabScene, material_transfer_progress
from miniatured_world.app.lab_layout import LabLayout

MATERIAL_COLORS = {"seed": "#98bc70", "water": "#83d8dd", "mineral": "#b0a0ee", "soil": "#b58a62", "sand": "#e5cc87", "food": "#e09d73"}


def load_hand_assets() -> dict[str, QPixmap]:
    data = motion_data()
    paths = {frame["hand_mask"] for clip in data["series"].values() for frame in clip["frames"]}
    paths.update(frame["hand_mask"] for frame in data["walking"])
    paths.update({"held/vial_empty.png", "held/vial_filled.png"})
    base = resources.files("miniatured_world") / "assets"
    result = {}
    for path in sorted(paths):
        image = QImage.fromData((base / path).read_bytes())
        if image.isNull() or not image.hasAlphaChannel():
            raise ValueError(f"手元の透過素材を読み込めません: {path}")
        result[path] = QPixmap.fromImage(image)
    return result


def scene_pose(scene: LabScene) -> MotionFrame | None:
    if scene.walk_frame is not None:
        frame = motion_data()["walking"][scene.walk_frame]
        return MotionFrame(frame["sprite"], frame["hand_mask"], tuple(frame["grip"]), 125)
    if scene.action_frame is not None:
        return motion_clip(scene.workflow_phase).frames[scene.action_frame]
    return None


def grip_position(scene: LabScene, layout: LabLayout) -> tuple[float, float] | None:
    pose = scene_pose(scene)
    if pose is None:
        return None
    x, y = scene.character_position
    gx, gy = pose.grip
    direction = -1 if scene.facing_right else 1
    return x + direction * (gx - 64) * layout.pixel_scale, y + (gy - 120) * layout.pixel_scale


def vessel_opening(scene: LabScene, layout: LabLayout) -> tuple[float, float] | None:
    grip = grip_position(scene, layout)
    if grip is None:
        return None
    data = motion_data()["vial"]
    dx, dy = (b - a for a, b in zip(data["grip"], data["opening"]))
    angle = math.radians(scene.vessel_angle)
    return (
        grip[0] + (dx * math.cos(angle) - dy * math.sin(angle)) * layout.pixel_scale,
        grip[1] + (dx * math.sin(angle) + dy * math.cos(angle)) * layout.pixel_scale,
    )


def page_corner(scene: LabScene, layout: LabLayout) -> tuple[float, float] | None:
    if scene.workflow_phase != "read" or scene.action_frame is None:
        return None
    clip = motion_clip("read")
    touch, release = clip.event_frame("touch"), clip.event_frame("release")
    if scene.action_frame < touch:
        return None
    if scene.action_frame < release:
        return grip_position(scene, layout)
    start_ms = clip.frame_start(release)
    settling_ms = 300
    if scene.action_elapsed_ms >= start_ms + settling_ms:
        return None
    previous = clip.frames[release - 1].grip
    x, y = scene.character_position
    start = (x + (64 - previous[0]) * layout.pixel_scale, y + (previous[1] - 120) * layout.pixel_scale)
    book = layout.gimmick("book")
    end = (book.position[0] + 14 * layout.pixel_scale, book.position[1] - book.size[1] + 14 * layout.pixel_scale)
    t = (scene.action_elapsed_ms - start_ms) / settling_ms
    return tuple(a + (b - a) * t for a, b in zip(start, end))


def _front(painter: QPainter, layout: LabLayout, key: str, sprite: QPixmap) -> None:
    item = layout.gimmick(key)
    x, y = item.position
    width, height = item.size
    if key == "cauldron":
        top = y - height * 104 / 112
        source_y = 52
        painter.drawPixmap(QRectF(x - width / 2, top + source_y * height / 112, width, (112 - source_y) * height / 112), sprite, QRectF(0, source_y, 96, 112 - source_y))
    else:
        ratio = .60 if key == "basket" else .625
        painter.drawPixmap(QRectF(x - width / 2, y - height * (1 - ratio), width, height * (1 - ratio)), sprite, QRectF(0, sprite.height() * ratio, sprite.width(), sprite.height() * (1 - ratio)))


def _fingers(painter: QPainter, scene: LabScene, layout: LabLayout, assets: dict[str, QPixmap]) -> None:
    pose = scene_pose(scene)
    if pose is None:
        return
    sprite = assets[pose.hand_mask]
    unit = layout.pixel_scale
    painter.save()
    painter.translate(*scene.character_position)
    if scene.facing_right:
        painter.scale(-1, 1)
    painter.drawPixmap(QRectF(-64 * unit, -120 * unit, 128 * unit, 128 * unit), sprite, QRectF(sprite.rect()))
    painter.restore()


def draw_hand_overlays(painter: QPainter, layout: LabLayout, props: dict[str, QPixmap], pot: QPixmap, scene: LabScene, assets: dict[str, QPixmap]) -> None:
    unit = layout.pixel_scale
    vial_data = motion_data()["vial"]
    vx, vy = vial_data["grip"]

    def bottle(position, *, contents="product", angle=0):
        materials = scene.batch_materials if contents == "materials" else ()
        if scene.workflow_phase == "arrive":
            materials = tuple(key for index, key in enumerate(materials) if material_transfer_progress("arrive", scene.action_progress, index, len(scene.batch_materials)) >= 1)
        filled = contents == "product" or bool(materials)
        sprite = assets[f'held/vial_{"filled" if filled else "empty"}.png']
        painter.save()
        painter.translate(*position)
        painter.rotate(angle)
        painter.drawPixmap(QRectF(-vx * unit, -vy * unit, 24 * unit, 32 * unit), sprite, QRectF(sprite.rect()))
        painter.setPen(Qt.PenStyle.NoPen)
        for index, key in enumerate(materials):
            painter.setBrush(QColor(MATERIAL_COLORS.get(key, "#b2d5a4")))
            painter.drawRect(QRectF((-2 + index % 3 * 2) * unit, (8 + index // 3 * 2) * unit, unit, unit))
        painter.restore()

    tray = layout.gimmick("product")
    tray_grip = (tray.position[0], tray.position[1] - 6 * unit - (vial_data["base"][1] - vy) * unit)
    incoming_contact = scene.workflow_phase == "place" and scene.action_frame is not None and scene.action_frame >= motion_clip("place").event_frame("contact")
    # トレーは最新成果の表示枠。接地した新しい瓶で旧表示を置き換え、
    # 握った瓶と旧表示が同じ場所へ二重に重ならないようにする。
    if scene.product_visible and not (incoming_contact and scene.tray_product_id != scene.cycle_id):
        bottle(tray_grip)
    if scene.vessel_location == "basket":
        basket = layout.gimmick("basket")
        bottle((basket.position[0], basket.position[1] - 15 * unit), contents=scene.vessel_contents)
    elif scene.vessel_location == "hand":
        grip = grip_position(scene, layout)
        if grip is not None:
            bottle(grip, contents=scene.vessel_contents, angle=scene.vessel_angle)

    corner = page_corner(scene, layout)
    if corner is not None:
        book = layout.gimmick("book")
        x, y = book.position
        top = y - book.size[1]
        painter.setPen(QPen(QColor("#a88a59"), unit))
        painter.setBrush(QColor("#f0dfad"))
        painter.drawPolygon(QPolygonF([QPointF(x, top + 5 * unit), QPointF(corner[0], corner[1] - 9 * unit), QPointF(*corner), QPointF(x - 3 * unit, top + 19 * unit)]))
    if scene.vessel_location == "hand" or scene.action_frame is not None:
        _fingers(painter, scene, layout, assets)
    if scene.vessel_location == "basket" or scene.workflow_phase == "collect":
        _front(painter, layout, "basket", props["basket"])
    if scene.workflow_phase == "mix":
        _front(painter, layout, "cauldron", pot)
    if scene.product_visible or scene.workflow_phase == "place":
        _front(painter, layout, "product", props["product"])
