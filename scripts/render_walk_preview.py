"""歩行8コマと左右向きの拡大プレビューを合成する。OS画面は撮影しない。"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageOps


def main() -> None:
    output = Path("docs/images")
    frames = []
    sheet = Image.new("RGB", (1024, 512), "#78695c")
    for index in range(8):
        sprite = Image.open(f"src/miniatured_world/assets/characters/alchemist_girl/walk_{index + 1:02}.png").convert("RGBA")
        sprite = sprite.resize((256, 256), Image.Resampling.NEAREST)
        sheet.paste(sprite, (index % 4 * 256, index // 4 * 256), sprite)
        frame = Image.new("RGB", (512, 280), "#78695c")
        draw = ImageDraw.Draw(frame)
        draw.line((0, 250, 512, 250), fill="#65564f", width=2)
        frame.paste(sprite, (0, 10), sprite)
        mirrored = ImageOps.mirror(sprite)
        frame.paste(mirrored, (256, 10), mirrored)
        frames.append(frame)
    sheet.save(output / "walking-frames.png")
    palette = sheet.quantize(colors=128)
    frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    frames[0].save(output / "walking-close.gif", save_all=True, append_images=frames[1:], duration=[70, 80] * 4, loop=0)


if __name__ == "__main__":
    main()
