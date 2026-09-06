"""歩行原画をv0.9.3と同じ64色/128pxへ整形し、manifestに追加する。"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path

from PIL import Image


def remove_background(image: Image.Image) -> Image.Image:
    """外縁に接続した無彩色の市松だけを抜く。服と反射の白は保持する。"""
    image = image.convert("RGBA")
    width, height = image.size
    pixels = list(image.get_flattened_data())
    eligible = bytearray(a < 160 or (min(r, g, b) >= 225 and max(r, g, b) - min(r, g, b) <= 18) for r, g, b, a in pixels)
    queue = deque(i for i in range(width * height) if (i < width or i >= width * (height - 1) or i % width in (0, width - 1)) and eligible[i])
    visited = bytearray(width * height)
    while queue:
        index = queue.popleft()
        if visited[index] or not eligible[index]:
            continue
        visited[index] = 1
        x, y = index % width, index // width
        for neighbor in (index - 1 if x else -1, index + 1 if x < width - 1 else -1, index - width if y else -1, index + width if y < height - 1 else -1):
            if neighbor >= 0 and not visited[neighbor] and eligible[neighbor]:
                queue.append(neighbor)
    image.putdata([(0, 0, 0, 0) if visited[i] or a < 160 else (r, g, b, 255) for i, (r, g, b, a) in enumerate(pixels)])
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("art/walking-v0.9.4/walk-sheet.png"))
    parser.add_argument("--output", type=Path, default=Path("src/miniatured_world/assets"))
    args = parser.parse_args()
    manifest_path = args.output / "sprites_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    palette = Image.new("P", (1, 1))
    colors = [value for color in manifest["palette"] for value in color]
    palette.putpalette(colors + colors[:3] * (256 - len(manifest["palette"])))
    sheet = remove_background(Image.open(args.input))
    if sheet.size != (1536, 1024):
        raise ValueError("記録済み歩行原画の寸法と違います")
    columns = (0, 400, 750, 1110, 1536)
    # 生成原画での腰の中心。セルの余白差を身体の横揺れへ持ち込まない。
    centers = (192, 548, 904, 1262, 184, 540, 896, 1254)
    frames = []
    for index, center in enumerate(centers):
        column, row = index % 4, index // 4
        cell = sheet.crop((columns[column], row * 500, columns[column + 1], 500 if row == 0 else 1024))
        left, top, right, bottom = cell.getbbox()
        cropped = cell.crop((left, top, right, bottom))
        scale = 104 / 384  # 全コマで同一縮尺。既存立ち絵と同じ身長。
        cropped = cropped.resize((round(cropped.width * scale), round(cropped.height * scale)), Image.Resampling.NEAREST)
        frame = Image.new("RGBA", (128, 128))
        frame.paste(cropped, (64 - round((center - columns[column] - left) * scale), 120 - cropped.height))
        # 顔・帽子の生成差を固定する。腕・裾・脚は各コマの原画を保つ。
        if frames:
            frame.paste(frames[0].crop((0, 0, 128, 72)), (0, 0))
        if index >= 4:
            # 後半は前に出る脚が奥側になる。明暗を交替し、同じ脚の
            # 足踏みに見える生成原画を補正する（輪郭と靴の向きは保持）。
            for y in range(96, 120):
                amount = min(1.0, (y - 95) / 6)
                for x in range(40, 100):
                    r, g, b, a = frame.getpixel((x, y))
                    if a and max(r, g, b) > 45:
                        factor = 1 - 0.25 * amount if x < 70 else 1 + 0.24 * amount
                        frame.putpixel((x, y), (min(255, round(r * factor)), min(255, round(g * factor)), min(255, round(b * factor)), a))
        quantized = frame.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA")
        quantized.putalpha(frame.getchannel("A"))
        quantized.putdata([p if p[3] else (0, 0, 0, 0) for p in quantized.get_flattened_data()])
        bounds = quantized.getbbox()
        if min(bounds[0], bounds[1], 128 - bounds[2], 128 - bounds[3]) < 4:
            raise ValueError(f"歩行{index + 1}の余白不足")
        frames.append(quantized)
    prefix = "characters/alchemist_girl/walk_"
    manifest["files"] = [record for record in manifest["files"] if not record["path"].startswith(prefix)]
    for index, frame in enumerate(frames, 1):
        name = f"{prefix}{index:02}.png"
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.save(path)
        manifest["files"].append({"path": name, "size": list(frame.size), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest["version"] = "0.9.4"
    manifest["sources"]["walking-v0.9.4/walk-sheet.png"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    manifest["walking"] = {"frames": 8, "facing": "left", "head_fixed_until_y": 72, "speed": 80, "stride": 48}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"歩行8コマ: {args.output}")


if __name__ == "__main__":
    main()
