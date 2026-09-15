"""利用可能画面へ自分のウィンドウを収める、Qtに依存しない計算。"""

from miniatured_world.persistence.settings import WindowSettings


def fit_window(
    window: WindowSettings,
    screens: list[tuple[int, int, int, int]],
    *,
    frame: tuple[int, int, int, int] = (0, 0, 0, 0),
    minimum: tuple[int, int] = (900, 620),
) -> WindowSettings:
    """screensは主画面を先頭にする。位置はフレーム、寸法は内容領域。"""
    available = [area for area in screens if area[2] > 0 and area[3] > 0]
    if not available:
        return window
    left, top, right, bottom = frame
    border_w, border_h = max(0, left + right), max(0, top + bottom)

    def intersection(area):
        x, y, width, height = area
        overlap_w = max(0, min(window.x + window.width + border_w, x + width) - max(window.x, x))
        overlap_h = max(0, min(window.y + window.height + border_h, y + height) - max(window.y, y))
        return overlap_w * overlap_h if window.saved else 0

    x, y, width, height = max(available, key=intersection)
    content_w = min(max(window.width, minimum[0]), max(1, width - border_w))
    content_h = min(max(window.height, minimum[1]), max(1, height - border_h))
    preferred_x = window.x if window.saved else x + (width - content_w - border_w) // 2
    preferred_y = window.y if window.saved else y + (height - content_h - border_h) // 2
    return WindowSettings(
        saved=True,
        x=max(x, min(preferred_x, x + width - content_w - border_w)),
        y=max(y, min(preferred_y, y + height - content_h - border_h)),
        width=content_w, height=content_h,
    )
