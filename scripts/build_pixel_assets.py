"""生成原画を共通の論理ピクセル・64色パレットへ変換する開発用処理。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageColor


STATES = ("idle", "work", "success", "failure", "rest")
CHARACTER_BOXES = ((0, 0, 380, 793), (380, 0, 790, 793), (790, 0, 1210, 793), (1210, 0, 1600, 793), (1600, 0, 1983, 793))
CHARACTER_CENTERS = (176, 584, 1002, 1402, 1786)


def silhouette(image: Image.Image) -> Image.Image:
    """真の生成透過を保ち、中間alphaを二値化して縁のぼけを除く。"""
    image = image.convert("RGBA")
    image.putalpha(image.getchannel("A").point(lambda value: 255 if value >= 160 else 0))
    if not image.getbbox():
        raise ValueError("空の透過画像です")
    return image


def fit_prop(path: Path, size: tuple[int, int]) -> Image.Image:
    image = silhouette(Image.open(path))
    image = image.crop(image.getbbox())
    image = image.resize(size, Image.Resampling.NEAREST)
    return image


def work_pose(path: Path) -> Image.Image:
    """単体原画の外側に接続した市松背景だけを除き、内部の白を保護する。"""
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    pixels = list(image.get_flattened_data())
    eligible = bytearray(min(r, g, b) >= 225 and max(r, g, b) - min(r, g, b) <= 18 for r, g, b, _ in pixels)
    queue = deque(i for i in range(width * height) if (i < width or i >= width * (height - 1) or i % width in (0, width - 1)) and eligible[i])
    visited = bytearray(width * height)
    while queue:
        index = queue.popleft()
        if visited[index] or not eligible[index]:
            continue
        visited[index] = 1
        x, y = index % width, index // width
        for neighbor in ((index - 1 if x else -1), (index + 1 if x < width - 1 else -1), (index - width if y else -1), (index + width if y < height - 1 else -1)):
            if neighbor >= 0 and not visited[neighbor] and eligible[neighbor]:
                queue.append(neighbor)
    image.putdata([(r, g, b, 0 if visited[i] else a) for i, (r, g, b, a) in enumerate(pixels)])
    image = silhouette(image)
    left, top, right, bottom = image.getbbox()
    scale = 104 / (bottom - top)
    cropped = image.crop((left, top, right, bottom))
    cropped = cropped.resize((round(cropped.width * scale), 104), Image.Resampling.NEAREST)
    output = Image.new("RGBA", (128, 128))
    output.paste(cropped, (64 - round((675 - left) * scale), 16))
    return output


def character_frames(path: Path) -> dict[str, Image.Image]:
    sheet = silhouette(Image.open(path))
    if sheet.size != (1983, 793):
        raise ValueError("記録済み原画シートの寸法と違います")
    result = {}
    for state, box, center in zip(STATES, CHARACTER_BOXES, CHARACTER_CENTERS):
        cell = sheet.crop(box)
        left, top, right, bottom = cell.getbbox()
        cropped = cell.crop((left, top, right, bottom))
        # 全ポーズで同じ縮尺。休憩や成功を個別の高さへ引き伸ばさない。
        scale = 0.21
        image = cropped.resize((round(cropped.width * scale), round(cropped.height * scale)), Image.Resampling.NEAREST)
        anchor = round((center - box[0] - left) * scale)
        output = Image.new("RGBA", (128, 128))
        output.paste(image, (64 - anchor, 120 - image.height))
        bounds = output.getbbox()
        if min(bounds[0], bounds[1], 128 - bounds[2], 128 - bounds[3]) < 4:
            raise ValueError(f"透明余白が足りません: {state}")
        result[f"characters/alchemist_girl/{state}.png"] = output
    return result


def cauldron_frames(path: Path) -> dict[str, Image.Image]:
    body = fit_prop(path, (80, 72))
    result = {}
    for state in ("idle", "receive", "failure", "success"):
        for frame in range(8):
            image = Image.new("RGBA", (96, 112))
            image.paste(body, (8, 32))
            draw = ImageDraw.Draw(image)
            dark, light = {
                "idle": ("#79abb2", "#c6dfd0"),
                "receive": ("#48a897", "#a5e6be"),
                "failure": ("#907497", "#d0a7b0"),
                "success": ("#9c77c3", "#ead2ff"),
            }[state]
            # 同じ本体に、整数ピクセルの湯気を描く。上部だけが動く。
            for step in range(8):
                y = 46 - step * 4
                x = 48 + round(math.sin(step * 0.8 + frame * math.tau / 8) * (2 + step / 2))
                width = 5 if step < 5 else 3
                draw.rectangle((x - width, y - 3, x + width, y), fill=dark)
                draw.rectangle((x - width + 2, y - 3, x + 1, y - 2), fill=light)
            if state != "idle":
                for index in range(3):
                    x = 27 + index * 21
                    y = 18 + (frame * 3 + index * 7) % 19
                    draw.line((x - 2, y, x + 2, y), fill=light)
                    draw.line((x, y - 2, x, y + 2), fill=light)
            result[f"cauldron/magic_cauldron/{state}_{frame + 1:02}.png"] = image
    return result


def shared_palette(images: dict[str, Image.Image]) -> tuple[dict[str, Image.Image], list[list[int]]]:
    # 素材ごとに同程度の重みを与え、人物の肌や小道具の色もパレットへ残す。
    selected = list(images)[:5] + [f"cauldron/magic_cauldron/{state}_01.png" for state in ("idle", "receive", "failure", "success")] + ["props/lectern.png", "props/basket.png", "props/tray.png"]
    samples = Image.new("RGB", (256, 256 * len(selected)), "#332b3d")
    for row, name in enumerate(selected):
        image = images[name].resize((256, 256), Image.Resampling.NEAREST)
        samples.paste(image, (0, row * 256), image)
    palette = samples.quantize(colors=56, method=Image.Quantize.MEDIANCUT)
    colors = palette.getpalette()[:56 * 3]
    for color in ("#79abb2", "#c6dfd0", "#48a897", "#a5e6be", "#907497", "#d0a7b0", "#9c77c3", "#ead2ff"):
        colors.extend(ImageColor.getrgb(color))
    palette.putpalette(colors + colors[:3] * 192)
    result = {}
    for name, image in images.items():
        quantized = image.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA")
        quantized.putalpha(image.getchannel("A"))
        quantized.putdata([pixel if pixel[3] else (0, 0, 0, 0) for pixel in quantized.get_flattened_data()])
        result[name] = quantized
    colors = palette.getpalette()[:64 * 3]
    return result, [colors[index:index + 3] for index in range(0, len(colors), 3)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("art/pixel-v0.9.3"))
    parser.add_argument("--output", type=Path, default=Path("logs/pixel-v0.9.3/candidates"))
    args = parser.parse_args()
    images = character_frames(args.input / "character-sheet.png")
    images["characters/alchemist_girl/work.png"] = work_pose(args.input / "work-pose.png")
    images.update(cauldron_frames(args.input / "cauldron.png"))
    for name, size in (("lectern", (48, 68)), ("basket", (52, 28)), ("tray", (48, 16))):
        images[f"props/{name}.png"] = fit_prop(args.input / f"{name}.png", size)
    images, palette = shared_palette(images)
    records = []
    for name, image in images.items():
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        records.append({"path": name, "size": image.size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    manifest = {"version": "0.9.3", "pixel_scale": 2, "character_canvas": [128, 128], "character_baseline": 120, "cauldron_canvas": [96, 112], "cauldron_baseline": 104, "palette": palette, "sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.input.glob("*.png"))}, "files": records}
    (args.output / "sprites_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(images)} sprites: {args.output}")


if __name__ == "__main__":
    main()
