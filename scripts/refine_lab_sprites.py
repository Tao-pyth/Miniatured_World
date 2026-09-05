"""既存PNGの外周だけを補正する候補生成器。入力を上書きしない。"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
from statistics import median

from PIL import Image


# 顔・白い服・瓶の反射は輪郭補正から保護する。座標は元192px素材。
PROTECTED = {
    "idle": ((70, 80, 110, 120), (70, 120, 112, 144), (34, 130, 49, 153)),
    "work": ((72, 95, 116, 132), (73, 135, 119, 160), (40, 132, 52, 155)),
    "success": ((71, 88, 116, 126), (73, 130, 112, 155), (41, 115, 53, 139)),
    "failure": ((64, 106, 113, 136), (58, 140, 125, 156)),
    "rest": ((98, 126, 136, 158),),
}


def clean_outline(image: Image.Image, protected: tuple[tuple[int, int, int, int], ...] = ()) -> Image.Image:
    """外周の無彩色マットを近傍の実色へ戻す。内部と保護領域は不変。"""
    result = image.convert("RGBA").copy()
    width, height = result.size
    for _ in range(2):
        source = result.copy()
        pixels, target = source.load(), result.load()
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                r, g, b, alpha = pixels[x, y]
                if not alpha or min(r, g, b) < 150 or max(r, g, b) - min(r, g, b) > 46:
                    continue
                if any(left <= x < right and top <= y < bottom for left, top, right, bottom in protected):
                    continue
                if all(pixels[x + dx, y + dy][3] >= 96 for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                    continue
                neighbors = []
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        if not (0 <= x + dx < width and 0 <= y + dy < height) or dx == dy == 0:
                            continue
                        color = pixels[x + dx, y + dy]
                        if color[3] >= 200 and max(color[:3]) < 180:
                            neighbors.append((dx * dx + dy * dy, color))
                if not neighbors:
                    continue
                foreground = min(neighbors, key=lambda item: item[0])[1]
                observed = (r + g + b) / 3
                pigment = sum(foreground[:3]) / 3
                coverage = max(0.0, min(1.0, (255 - observed) / max(1, 255 - pigment)))
                target[x, y] = (*foreground[:3], round(alpha * coverage))
    return result


def align_baseline(image: Image.Image, baseline: int) -> tuple[Image.Image, int, int]:
    """本体より下に孤立した無彩色の走査線残骸を除き、接地をそろえる。"""
    image = image.copy()
    width, height = image.size
    pixels = image.load()
    remaining = {(x, y) for y in range(height) for x in range(width) if pixels[x, y][3]}
    components = []
    while remaining:
        first = remaining.pop()
        queue, component = deque([first]), {first}
        while queue:
            x, y = queue.popleft()
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    queue.append(point)
        components.append(component)
    body = max(components, key=len)
    bottom = max(y for _, y in body)
    removed = 0
    for component in components:
        if len(component) <= 8 and min(y for _, y in component) > bottom + 3:
            if all(max(pixels[x, y][:3]) - min(pixels[x, y][:3]) <= 50 for x, y in component):
                for point in component:
                    pixels[point] = (0, 0, 0, 0)
                    removed += 1
    bounds = image.getbbox()
    dy = baseline - bounds[3]
    if bounds[1] + dy < 4 or baseline > height - 4:
        raise ValueError("接地補正が透明余白を越えます")
    output = Image.new("RGBA", image.size)
    output.paste(image, (0, dy))
    return output, dy, removed


def register_body(image: Image.Image, *, cauldron: bool, resting: bool = False) -> tuple[Image.Image, int]:
    """本体の接地中心を合わせる。周辺記号や蒸気で中心を決めない。"""
    width, height = image.size
    pixels = image.load()
    remaining = {(x, y) for y in range(height) for x in range(width) if pixels[x, y][3] >= 128}
    components = []
    while remaining:
        first = remaining.pop()
        queue = deque([first])
        component = {first}
        while queue:
            x, y = queue.popleft()
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point in remaining:
                    remaining.remove(point)
                    component.add(point)
                    queue.append(point)
        components.append(component)
    if not components:
        raise ValueError("本体の画素がありません")
    body = max(components, key=len)
    bottom = max(y for _, y in body)
    band = [(x, y) for x, y in body if y >= bottom - (20 if cauldron else 8)]
    if resting:
        center = (min(x for x, _ in body) + max(x for x, _ in body)) / 2
    else:
        centers = []
        for y in sorted({y for _, y in band}):
            row = [x for x, py in band if py == y]
            centers.append((min(row) + max(row)) / 2)
        center = median(centers)
    bounds = image.getbbox()
    requested = round(width / 2 - center)
    shift = max(4 - bounds[0], min(width - 4 - bounds[2], requested))
    output = Image.new("RGBA", image.size)
    output.paste(image, (shift, 0))
    return output, shift


def stabilize_cauldron_frames(frames: list[Image.Image]) -> list[Image.Image]:
    """本体の描線の揺れを除き、湯気・口・火のアニメーションを残す。"""
    body = frames[0].crop((0, 74, 96, 128))
    result = []
    for frame in frames:
        output = frame.copy()
        fire = frame.crop((34, 105, 63, 116))
        output.paste(body, (0, 74))
        output.paste(fire, (34, 105))
        result.append(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="元のassetsディレクトリ")
    parser.add_argument("--output", type=Path, required=True, help="補正候補の別ディレクトリ")
    args = parser.parse_args()
    source_root, output_root = args.input.resolve(), args.output.resolve()
    if source_root == output_root or source_root in output_root.parents:
        parser.error("候補の出力先は入力素材ディレクトリの外にしてください")
    report = []
    paths = sorted(source_root.glob("characters/alchemist_girl/*.png")) + sorted(source_root.glob("cauldron/magic_cauldron/*.png"))
    if len(paths) != 37:
        parser.error("人物5枚・釜32枚の元PNGが必要です")
    for path in paths:
        cauldron = path.parent.name == "magic_cauldron"
        original = Image.open(path).convert("RGBA")
        if original.size != ((96, 128) if cauldron else (192, 192)):
            raise ValueError(f"未対応の元素材サイズ: {path.name}")
        protected = ((0, 0, 96, 73),) if cauldron else PROTECTED[path.stem]
        cleaned = clean_outline(original, protected)
        grounded, dy, removed = align_baseline(cleaned, 120 if cauldron else 180)
        registered, dx = register_body(grounded, cauldron=cauldron, resting=path.stem == "rest")
        relative = path.relative_to(source_root)
        target = output_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        registered.save(target)
        changed = sum(a != b for a, b in zip(original.get_flattened_data(), cleaned.get_flattened_data()))
        report.append({"path": relative.as_posix(), "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "changed_outline_pixels": changed, "removed_scanline_pixels": removed, "horizontal_shift": dx, "vertical_shift": dy})
    for state in ("idle", "receive", "failure", "success"):
        paths = [output_root / f"cauldron/magic_cauldron/{state}_{i:02d}.png" for i in range(1, 9)]
        stabilized = stabilize_cauldron_frames([Image.open(path).convert("RGBA") for path in paths])
        for path, image in zip(paths, stabilized):
            image.save(path)
            record = next(item for item in report if item["path"] == path.relative_to(output_root).as_posix())
            record["body_reference"] = f"{state}_01.png"
            record["stable_body_from_y"] = 74
            record["animated_fire_xyxy"] = [34, 105, 63, 116]
            record["output_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output_root / "refinement-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{len(report)}枚の候補を保存しました: {output_root}")


if __name__ == "__main__":
    main()
