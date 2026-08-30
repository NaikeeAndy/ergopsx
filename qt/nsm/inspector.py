"""Панель разбора справа: всё, что движок знает о выделенном сейве."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from . import digest, icons
from . import lang
from .theme import Palette


def _label(text, kind=None, size=12.5, bold=False):
    made = QLabel(str(text))
    if kind:
        made.setObjectName(kind)
    font = made.font()
    font.setPointSizeF(size)
    if bold:
        font.setWeight(QFont.DemiBold)
    made.setFont(font)
    made.setWordWrap(True)
    return made


class Inspector(QScrollArea):
    def __init__(self, library, palette: Palette, parent=None):
        super().__init__(parent)
        self.library = library
        self.p = palette
        self.setWidgetResizable(True)
        self.body = QWidget()
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(18, 16, 18, 18)
        self.box.setSpacing(14)
        self.setWidget(self.body)
        self.show_item(None)

    def _clear(self):
        while self.box.count():
            got = self.box.takeAt(0)
            if got.widget():
                got.widget().deleteLater()

    def show_item(self, item):
        self._clear()
        if item is None:
            self.box.addWidget(_label(lang.t("Nothing selected"), "dim"))
            self.box.addStretch(1)
            return

        detail = self.library.detail(item)
        self.box.addWidget(self._head(item, detail))
        self.box.addWidget(self._grid([
            (lang.t("Serial"), item.serial), (lang.t("Region"), item.region),
            (lang.t("Blocks"), str(item.blocks)), (lang.t("Save name"), self._name(item)),
        ]))

        made = digest.build(detail)
        if made is None:
            self.box.addWidget(self._rule())
            self.box.addWidget(_label(
                lang.t("No detailed parser for this game — only the basics are shown: game, region, signature and icon."),
                "faint", 11.5))
            self.box.addStretch(1)
            return

        self.box.addWidget(self._rule())
        self.box.addWidget(_label(made.game.upper(), "head", 11))
        if made.fields:
            self.box.addWidget(self._grid(
                [(f.label, f.value) for f in made.fields]))

        if made.members:
            self.box.addWidget(self._rule())
            self.box.addWidget(_label(
                f"{made.members_title.upper()} · {len(made.members)}", "head", 11))
            for unit in made.members:
                self.box.addWidget(self._member(unit))

        for part in made.sections:
            self.box.addWidget(self._rule())
            head = part.title.upper()
            if part.note:
                head += f" · {part.note}"
            self.box.addWidget(_label(head, "head", 11))
            self.box.addWidget(self._flow(
                [f"{f.label}  {f.value}".strip() for f in part.items]))

        self.box.addStretch(1)

    def _name(self, item):
        raw = bytes(item.frame[10:30]).split(b"\x00")[0]
        return raw.decode("ascii", "replace")

    def _head(self, item, detail):
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(14)

        picture = QLabel()
        pictures = icons.frames(item.block, item.fingerprint, side=64)
        if pictures:
            picture.setPixmap(pictures[0])
        picture.setFixedSize(64, 64)
        line.addWidget(picture)

        text = QWidget()
        column = QVBoxLayout(text)
        column.setContentsMargins(0, 4, 0, 0)
        column.setSpacing(3)
        column.addWidget(_label(item.title, size=17, bold=True))
        second = item.signature or item.serial
        if detail.get("progress"):
            second += f"   ({detail['progress']}%)"
        column.addWidget(_label(second, "dim", 12))
        line.addWidget(text, 1)
        return row

    def _member(self, unit):
        """Строка бойца: имя, роль, уровень, числа и что надето."""
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 2, 0, 6)
        column.setSpacing(2)

        top = QWidget()
        line = QHBoxLayout(top)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(8)
        line.addWidget(_label(unit.name, size=12.5, bold=True))
        if unit.level:
            line.addWidget(_label(lang.t("lv. {0}", unit.level), "accent", 11.5))
        if unit.role:
            line.addWidget(_label(unit.role, "dim", 11.5))
        line.addStretch(1)
        column.addWidget(top)

        numbers = " · ".join(f"{f.label} {f.value}" for f in unit.stats)
        if unit.extra:
            numbers += ("  ·  " if numbers else "") + unit.extra
        if numbers:
            column.addWidget(_label(numbers, "dim", 11.5))
        if unit.gear:
            column.addWidget(_label(" · ".join(unit.gear), "faint", 11))
        return box

    def _grid(self, pairs):
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(7)
        for index, (name, value) in enumerate(pairs):
            row, column = divmod(index, 2)
            grid.addWidget(_label(name, "dim", 12), row, column * 2)
            grid.addWidget(_label(value, size=12, bold=True), row, column * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        return box

    def _flow(self, values):
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(5)
        columns = 3
        for index, value in enumerate(values[:120]):
            grid.addWidget(_label(value, size=11.5),
                           index // columns, index % columns)
        return box

    def _rule(self):
        line = QFrame()
        line.setObjectName("hdivider")
        line.setFixedHeight(1)
        return line
