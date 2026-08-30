"""Список сейвов: одна колонка карточек с иконкой, подписью и временем."""

from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QStyle,
                               QStyledItemDelegate)

from . import icons
from . import lang
from .theme import Palette

ROW = 68


class SaveDelegate(QStyledItemDelegate):
    """Карточка рисуется вручную: так она выглядит одинаково везде."""

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self.p = palette
        self.frame = 0

    def sizeHint(self, option, index):
        return QSize(320, ROW)

    def paint(self, painter: QPainter, option, index):
        item = index.data(Qt.UserRole)
        if item is None:
            return
        p = self.p
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        box = option.rect.adjusted(2, 3, -2, -3)
        chosen = bool(option.state & QStyle.State_Selected)

        painter.setBrush(QColor(p.tile[0]))
        painter.setPen(QPen(QColor(p.accent if chosen else p.tile_edge),
                            1.5 if chosen else 1))
        painter.drawRoundedRect(box, 9, 9)

        pictures = icons.frames(item.block, item.fingerprint, side=46)
        if pictures:
            picture = pictures[self.frame % len(pictures)]
            painter.drawPixmap(box.left() + 11, box.top() + 10, picture)

        left = box.left() + 68
        width = box.width() - 78

        font = painter.font()
        font.setPointSizeF(12.5)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(p.ink))
        painter.drawText(left, box.top() + 24,
                         painter.fontMetrics().elidedText(
                             item.title, Qt.ElideRight, width))

        font.setPointSizeF(10.5)
        font.setWeight(QFont.Normal)
        font.setFamily("Menlo, Consolas, DejaVu Sans Mono, monospace")
        painter.setFont(font)
        painter.setPen(QColor(p.ink_soft))
        second = item.signature or item.serial
        painter.drawText(left, box.top() + 41,
                         painter.fontMetrics().elidedText(
                             second, Qt.ElideRight, width))

        painter.setPen(QColor(p.ink_faint))
        third = lang.t("{0} · {1} bl.", item.region, item.blocks)
        if item.folder:
            third += f" · {item.folder}"
        # Место под время держим всегда: без запаса третья строка
        # наезжала на него и получалась каша из цифр.
        painter.drawText(left, box.top() + 57,
                         painter.fontMetrics().elidedText(
                             third, Qt.ElideRight, max(40, width - 76)))

        if item.clock:
            painter.setPen(QColor(p.accent))
            # Прямоугольник задаётся верхним краем, а не базовой линией:
            # с 57 время уезжало за нижнюю границу карточки.
            painter.drawText(box.right() - 64, box.top() + 44, 56, 16,
                             Qt.AlignRight | Qt.AlignVCenter, item.clock)
        painter.restore()


class SaveList(QListWidget):
    chosen = Signal(object)

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self.delegate = SaveDelegate(palette, self)
        self.setItemDelegate(self.delegate)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setUniformItemSizes(True)
        self.currentItemChanged.connect(self._changed)

        # Многокадровые иконки крутятся, как их крутил BIOS.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(180)

    def _tick(self):
        self.delegate.frame += 1
        self.viewport().update()

    def _changed(self, current, _previous):
        self.chosen.emit(current.data(Qt.UserRole) if current else None)

    def show_items(self, items):
        self.clear()
        for item in items:
            row = QListWidgetItem()
            row.setData(Qt.UserRole, item)
            self.addItem(row)
        if items:
            self.setCurrentRow(0)

    def selected(self):
        return [row.data(Qt.UserRole) for row in self.selectedItems()]
