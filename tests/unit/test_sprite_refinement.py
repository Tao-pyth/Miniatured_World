"""補正器の合成画素テスト。実素材への実行とは分離する。"""

import importlib.util
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")
spec = importlib.util.spec_from_file_location("refine_lab_sprites", Path(__file__).resolve().parents[2] / "scripts/refine_lab_sprites.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_cleanup_changes_only_light_outline_and_preserves_protected_highlights():
    original = Image.new("RGBA", (16, 16))
    for y in range(4, 12):
        for x in range(4, 12):
            original.putpixel((x, y), (70, 40, 30, 255))
    original.putpixel((4, 7), (220, 220, 220, 255))
    original.putpixel((7, 7), (250, 249, 240, 255))
    original.putpixel((11, 7), (250, 249, 240, 255))
    output = module.clean_outline(original, ((11, 7, 12, 8),))
    assert output.getpixel((4, 7))[:3] == (70, 40, 30)
    assert 0 < output.getpixel((4, 7))[3] < 255
    assert output.getpixel((7, 7)) == original.getpixel((7, 7))
    assert output.getpixel((11, 7)) == original.getpixel((11, 7))
    assert output.getpixel((6, 6)) == original.getpixel((6, 6))
    assert original.getpixel((4, 7)) == (220, 220, 220, 255)


def test_registration_ignores_detached_sparkles_and_does_not_clip_them():
    image = Image.new("RGBA", (32, 32))
    for y in range(10, 26):
        for x in range(18, 24):
            image.putpixel((x, y), (60, 40, 30, 255))
    image.putpixel((10, 5), (255, 215, 60, 255))
    output, shift = module.register_body(image, cauldron=False)
    assert shift == -4
    assert sum(pixel[3] > 0 for pixel in image.get_flattened_data()) == sum(pixel[3] > 0 for pixel in output.get_flattened_data())
    assert output.getpixel((6, 5)) == (255, 215, 60, 255)


def test_grounding_removes_only_isolated_neutral_scanline_below_body():
    image = Image.new("RGBA", (32, 32))
    for y in range(10, 24):
        for x in range(12, 22):
            image.putpixel((x, y), (60, 40, 30, 255))
    image.putpixel((8, 5), (255, 215, 60, 255))
    image.putpixel((16, 29), (215, 215, 215, 255))
    output, shift, removed = module.align_baseline(image, 28)
    assert shift == 4
    assert removed == 1
    assert output.getbbox()[3] == 28
    assert output.getpixel((8, 9)) == (255, 215, 60, 255)
    assert sum(p[3] > 0 for p in output.get_flattened_data()) == 141


def test_cauldron_body_is_stable_while_fire_and_steam_remain_animated():
    first = Image.new("RGBA", (96, 128), (80, 40, 20, 255))
    second = Image.new("RGBA", (96, 128), (90, 50, 30, 255))
    first.putpixel((48, 30), (120, 240, 210, 255))
    second.putpixel((48, 30), (190, 250, 220, 255))
    first.putpixel((48, 110), (255, 160, 30, 255))
    second.putpixel((48, 110), (255, 220, 40, 255))
    a, b = module.stabilize_cauldron_frames([first, second])
    assert a.getpixel((20, 90)) == b.getpixel((20, 90))
    assert a.getpixel((48, 30)) != b.getpixel((48, 30))
    assert a.getpixel((48, 110)) != b.getpixel((48, 110))
