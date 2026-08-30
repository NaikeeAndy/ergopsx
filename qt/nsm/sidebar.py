"""Боковой список - только места, где лежат сейвы.

Действия сюда не попадают: они над выделенным, наверху. Раскладка та же,
что в версии для macOS: разделы, цветная метка у каждой строки и счётчик
справа.
"""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QStyle,
                               QStyledItemDelegate)

from . import lang
from .theme import Palette

HEAD = 30       # высота заголовка раздела
ROW = 29        # высота строки


class Delegate(QStyledItemDelegate):
    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self.p = palette

    def sizeHint(self, option, index):
        head = index.data(Qt.UserRole + 1) == "head"
        return QSize(200, HEAD if head else ROW)

    def paint(self, painter: QPainter, option, index):
        p = self.p
        text = index.data(Qt.DisplayRole) or ""
        kind = index.data(Qt.UserRole + 1)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        box = option.rect

        if kind == "head":
            font = painter.font()
            font.setPointSizeF(10.5)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(p.ink_faint))
            painter.drawText(box.adjusted(10, 10, -8, 0), Qt.AlignLeft, text)
            painter.restore()
            return

        chosen = bool(option.state & QStyle.State_Selected)
        inner = box.adjusted(6, 1, -6, -1)
        if chosen:
            painter.setBrush(QColor(p.accent))
            painter.setOpacity(0.30)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(inner, 6, 6)
            painter.setOpacity(1.0)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(p.accent), 1.5))
            painter.drawRoundedRect(inner, 6, 6)

        # Цветная метка: четыре цвета логотипа по кругу.
        mark = index.data(Qt.UserRole + 2) or p.marks[0]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(mark))
        painter.drawRoundedRect(inner.left() + 8, inner.center().y() - 3,
                                7, 7, 2, 2)

        count = index.data(Qt.UserRole + 3)
        font = painter.font()
        font.setPointSizeF(13)
        font.setWeight(QFont.DemiBold if chosen else QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor(p.ink))
        room = inner.width() - 26 - (34 if count is not None else 0)
        painter.drawText(inner.left() + 23, inner.top(), room, inner.height(),
                         Qt.AlignVCenter | Qt.AlignLeft,
                         painter.fontMetrics().elidedText(
                             text, Qt.ElideRight, room))

        if count is not None:
            font.setPointSizeF(10.5)
            font.setWeight(QFont.Normal)
            font.setFamily("Menlo")
            painter.setFont(font)
            painter.setPen(QColor(p.ink_faint))
            painter.drawText(inner.right() - 36, inner.top(), 32, inner.height(),
                             Qt.AlignVCenter | Qt.AlignRight, str(count))
        painter.restore()


class Sidebar(QListWidget):
    picked = Signal(str)

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self.p = palette
        self.setItemDelegate(Delegate(palette, self))
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.currentItemChanged.connect(self._changed)

    def _changed(self, current, _previous):
        if current is None:
            return
        if current.data(Qt.UserRole + 1) == "head":
            return
        self.picked.emit(current.data(Qt.UserRole))

    def _head(self, text):
        row = QListWidgetItem(text)
        row.setData(Qt.UserRole + 1, "head")
        row.setFlags(Qt.NoItemFlags)          # заголовок не выбирается
        self.addItem(row)

    def _row(self, text, target, count=None, mark=None):
        row = QListWidgetItem(text)
        row.setData(Qt.UserRole, target)
        row.setData(Qt.UserRole + 2, mark)
        row.setData(Qt.UserRole + 3, count)
        row.setToolTip(text)
        self.addItem(row)

    def fill(self, library):
        self.clear()
        marks = self.p.marks
        self._head(lang.t("КОЛЛЕКЦИЯ", "COLLECTION"))
        self._row(lang.t("Все сейвы", "All saves"), "*", len(library.unique), marks[0])
        self._row(lang.t("Образы карт", "Card images"), "#cards", library.cards, marks[2])
        if library.games:
            self._head(lang.t(f"ИГРЫ · {len(library.games)}", f"GAMES · {len(library.games)}"))
            for index, (name, count) in enumerate(library.games):
                self._row(name, name, count, marks[(index + 1) % len(marks)])
        # Первая выбираемая строка - «Все сейвы».
        self.setCurrentRow(1)
