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
    # Панель у Swift лежит поверх градиента с прозрачностью 0.55, и сквозь
    # неё виден фон. Сплошная заливка тем же цветом даёт заметно другой
    # оттенок - именно на этом два приложения и разошлись по виду.
    panel_alpha: float
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
    panel_alpha=0.55,
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
    panel_alpha=0.55,
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


def _mix(one, two, part):
    """Смешивает два цвета: `part` - доля второго."""
    a = [int(one.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(two.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * part):02X}" for x, y in zip(a, b))


def _shift(color, part):
    """Двигает цвет к чёрному (part < 0) или к белому (part > 0)."""
    return _mix(color, "#FFFFFF" if part > 0 else "#000000", abs(part))


def _light(color):
    """Яркость по восприятию, 0..255."""
    r, g, b = (int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return (r * 299 + g * 587 + b * 114) / 1000


def _apart(color, amount):
    """Отодвигает цвет от исходного в ту сторону, где есть запас.

    Осветлять почти белое некуда: у Breeze Light фон `#eff0f1`, и плитки,
    построенные осветлением, сливались с ним. У наших палитр фон средней
    светлоты, и там это не всплывало.
    """
    return _shift(color, -amount if _light(color) > 160 else amount)


def _readable(color, on, gap=70):
    """Отодвигает цвет от фона, пока разница яркости не станет заметной.

    Акцент у нас служит и заливкой кнопки, и цветом текста. Как заливка
    системный `Highlight` хорош всегда, а как текст - нет: macOS отдаёт
    тёмно-синий `#314F78`, и на плитке он пропадает. Двигаем в сторону,
    противоположную фону.
    """
    toward = 1 if _light(on) < 128 else -1
    for step in range(0, 11):
        moved = _shift(color, toward * step * 0.07)
        if abs(_light(moved) - _light(on)) >= gap:
            return moved
    return moved


def from_system(qt_palette):
    """Палитра из цветов темы операционной системы.

    Нужна на Linux, где у пользователя единая тема на весь рабочий стол:
    KDE отдаёт свою цветовую схему через `QPalette`, и приложение,
    которое её не слушает, выглядит чужим среди остальных. Наши две
    темы никуда не деваются - это третий выбор, а не замена.

    Роли берутся стандартные, так что работает и в GNOME, и в Xfce -
    везде, где тема доходит до Qt.
    """
    from PySide6.QtGui import QPalette

    def color(role, group=QPalette.ColorGroup.Active):
        return qt_palette.color(group, getattr(QPalette.ColorRole, role)).name()

    window, text = color("Window"), color("WindowText")
    base, alt = color("Base"), color("AlternateBase")
    button, mid = color("Button"), color("Mid")
    highlight, on_highlight = color("Highlight"), color("HighlightedText")
    # Светлая тема или тёмная - по яркости фона, а не по названию:
    # названия у схем KDE произвольные.
    r, g, b = (int(window.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    light = (r * 299 + g * 587 + b * 114) / 1000 > 128

    # Направление сдвигов у обеих наших палитр одинаковое и от светлоты
    # темы не зависит: панель темнее фона, плитка и верхняя полоса -
    # светлее. Фон идёт сверху вниз от светлого к тёмному.
    # Плитка строится из фона, а не из `AlternateBase`. Роль эта - для
    # чередующихся строк таблицы, и системы понимают её по-разному:
    # macOS отдаёт средне-серый `#989898` при фоне `#323232`, и плитки
    # выходили светло-серыми посреди тёмного окна. От фона надёжнее
    # везде, а у наших палитр так и сделано.
    tile_top, tile_bottom = _apart(window, 0.11), _apart(window, 0.06)
    return Palette(
        background=(_shift(window, 0.05), window, _shift(window, -0.09)),
        bar=(_apart(button, 0.06), _apart(button, 0.01)),
        bar_line=mid,
        panel=_apart(window, -0.12),
        panel_alpha=0.55,
        panel_line=mid,
        tile=(tile_top, tile_bottom),
        tile_edge=_apart(window, 0.20),
        control=button,
        control_edge=mid,
        well=base,
        ink=text,
        # Приглушённые оттенки подмешиваются к **плитке**, а не к фону:
        # на ней этот текст чаще всего и лежит. Подмешивание к фону
        # давало серое по серому там, где плитка светлее окна.
        ink_soft=_mix(text, tile_top, 0.30),
        ink_faint=_mix(text, tile_top, 0.52),
        # Акцент читаемый на плитке: на ней он и лежит текстом.
        accent=_readable(highlight, tile_top),
        accent_ink=on_highlight,
        icon_well=_shift(base, -0.06),
        icon_well_edge=mid,
        # Четыре цвета логотипа остаются своими: это опознавательный знак
        # игр в списке, а не оформление.
        marks=DARK.marks,
        letterpress=light)


def rgba(hexcolor, alpha):
    """`#RRGGBB` плюс прозрачность - в вид, понятный Qt."""
    value = hexcolor.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha})"


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


def palette_for(name):
    """Палитра по имени темы из настроек."""
    if name == "system":
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            return from_system(app.palette())
    return LIGHT if name == "light" else DARK
