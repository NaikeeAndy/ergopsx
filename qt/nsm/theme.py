"""Палитра приложения - те же цвета, что в версии для macOS.

Две темы: светлая - корпус приставки, тёмная - экран карт памяти BIOS.
Значения перенесены из `swift/Sources/MemCardApp/Theme.swift` один в один,
чтобы обе версии выглядели одинаково.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Palette:
    background: tuple          # градиент фона: упоры сверху вниз
    bar: tuple                 # панель сверху и снизу
    bar_line: str
    panel: str
    panel_line: str
    tile: tuple                # плитка сейва
    tile_edge: str
    control: str
    control_edge: str
    well: str
    ink: str
    ink_soft: str
    ink_faint: str
    accent: str
    accent_ink: str
    icon_well: str
    icon_well_edge: str
    # Метки игр: четыре цвета логотипа в тёмной теме и четыре значка
    # с геймпада в светлой.
    marks: tuple
    # Гравировка по пластику - только в светлой теме.
    letterpress: bool = False


DARK = Palette(
    background=("#16233F", "#0D1526", "#080C16"),
    bar=("#1D2E4E", "#142138"),
    bar_line="#0A1120",
    panel="#090F1B",
    panel_line="#16233A",
    tile=("#22355A", "#172742"),
    tile_edge="#2C4470",
    control="#16243C",
    control_edge="#2A3E5E",
    well="#0C1424",
    ink="#E8EEF8",
    ink_soft="#9FB3D2",
    ink_faint="#5C7099",
    accent="#F2B705",
    accent_ink="#08101F",
    icon_well="#070C16",
    icon_well_edge="#2C4470",
    marks=("#F2B705", "#2E7CD6", "#2FA84F", "#E8433F"),
)

LIGHT = Palette(
    background=("#C9C5BB", "#C9C5BB"),
    bar=("#D6D2C8", "#C4C0B6"),
    bar_line="#A9A69D",
    panel="#C3BFB5",
    panel_line="#ABA79E",
    tile=("#DBD7CD", "#CAC6BC"),
    tile_edge="#ABA79E",
    control="#DEDAD0",
    control_edge="#ABA79E",
    well="#BFBBB1",
    ink="#2E2C28",
    ink_soft="#6B675F",
    ink_faint="#7C7870",
    accent="#C9A24C",
    accent_ink="#33301F",
    icon_well="#4A4740",
    icon_well_edge="#9A968D",
    marks=("#C9A24C", "#5B7BB0", "#5E9E77", "#C4636F"),
    letterpress=True,
)

GOOD = "#2FA84F"
BAD = "#E8433F"


def gradient(stops, horizontal=False):
    """Градиент для таблицы стилей Qt."""
    line = ("x1:0, y1:0, x2:1, y2:0" if horizontal
            else "x1:0, y1:0, x2:0, y2:1")
    if len(stops) == 1:
        return stops[0]
    parts = ", ".join(
        f"stop:{i / (len(stops) - 1):.3f} {colour}"
        for i, colour in enumerate(stops))
    return f"qlineargradient({line}, {parts})"
