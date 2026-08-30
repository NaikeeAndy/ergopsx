"""Полоса корзины внизу окна: пятнадцать слотов карты и две кнопки.

Всегда на виду, а не отдельным режимом: карта почти всегда собирается из
разных мест сразу, и отдельным экраном пришлось бы всё искать заново.
"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from .basket import SLOTS, blocks_word, saves_word
from . import icons, lang
from .theme import Palette

CELL = 34          # ширина слота
PITCH = CELL + 4
ICON = 24          # иконка внутри слота: поля 5 по бокам, 8 сверху и снизу


class Cells(QWidget):
    """Пятнадцать слотов карты — с иконками тех сейвов, что в них лежат.

    Иконка узнаётся с одного взгляда, а инициалы вроде «FFI» - нет:
    в корзине обычно лежат сейвы одной игры, и все подписи выходили
    одинаковыми. У многоблочного сейва цепочка видна по бледным
    ячейкам-продолжениям с той же иконкой.
    """

    def __init__(self, basket, palette: Palette, parent=None):
        super().__init__(parent)
        self.basket = basket
        self.p = palette
        self.frame = 0
        self.setFixedSize(SLOTS * PITCH - (PITCH - CELL), 44)
        # Многокадровые иконки крутятся, как их крутил BIOS.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(180)

    def _tick(self):
        self.frame += 1
        if any(item is not None for item, _ in self.basket.layout()):
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for index, (item, tail) in enumerate(self.basket.layout()):
            left, top = index * PITCH, 2
            if item is None:
                painter.setPen(QColor(self.p.tile_edge))
                painter.setBrush(QColor(self.p.well))
                painter.drawRoundedRect(left, top, CELL, 40, 5, 5)
                continue

            edge = QColor(self.p.accent)
            if tail:
                edge.setAlpha(120)
            painter.setPen(edge)
            painter.setBrush(QColor(self.p.tile[0]))
            painter.drawRoundedRect(left, top, CELL, 40, 5, 5)

            pictures = icons.frames(item.block, item.fingerprint, side=ICON)
            if not pictures:
                continue
            # Продолжение бледнее: так видно, что блок занят тем же сейвом.
            painter.setOpacity(0.45 if tail else 1.0)
            painter.drawPixmap(left + (CELL - ICON) // 2, top + (40 - ICON) // 2,
                               pictures[self.frame % len(pictures)])
            painter.setOpacity(1.0)


class BasketBar(QWidget):
    changed = Signal()

    def __init__(self, basket, palette: Palette, parent=None):
        super().__init__(parent)
        self.basket = basket
        self.p = palette
        self.setObjectName("bar")
        self.setFixedHeight(78)

        line = QHBoxLayout(self)
        line.setContentsMargins(16, 0, 16, 0)
        line.setSpacing(14)

        title = QLabel(lang.t("CARD"))
        title.setObjectName("head")
        line.addWidget(title)

        self.cells = Cells(basket, palette)
        line.addWidget(self.cells)

        text = QWidget()
        column = QVBoxLayout(text)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        self.line1 = QLabel()
        self.line2 = QLabel()
        self.line2.setObjectName("faint")
        font = self.line2.font()
        font.setPointSizeF(10.5)
        font.setFamily("Menlo")
        self.line2.setFont(font)
        column.addWidget(self.line1)
        column.addWidget(self.line2)
        line.addWidget(text, 1)

        self.clear_button = QPushButton(lang.t("Clear"))
        self.clear_button.clicked.connect(self._clear)
        line.addWidget(self.clear_button)

        self.save_button = QPushButton(lang.t("To file"))
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self._save)
        line.addWidget(self.save_button)
        self.refresh()

    def refresh(self):
        empty = not self.basket.items
        self.line1.setText(
            self.basket.note or
            (lang.t("Empty — add saves as you go, from anywhere") if empty
             else f"{len(self.basket.items)} {saves_word(len(self.basket.items))}"))
        self.line2.setText(
            lang.t("{0} of {1} blocks used", self.basket.used, SLOTS))
        self.clear_button.setEnabled(not empty)
        self.save_button.setEnabled(not empty)
        self.cells.update()
        self.changed.emit()

    def _clear(self):
        self.basket.clear()
        self.refresh()

    def _save(self):
        target, _ = QFileDialog.getSaveFileName(
            self, lang.t("The built card — original files are not changed"),
            "card.mcr", lang.t("Card image (*.mcr *.mcd *.VM1)"))
        if not target:
            return
        try:
            image, layout, dropped = self.basket.build()
        except Exception as error:
            QMessageBox.warning(self, lang.t("Build failed"), str(error))
            return
        with open(target, "wb") as fh:
            fh.write(image)
        note = lang.t("Built: {0} {1}", len(layout), saves_word(len(layout)))
        if dropped:
            note += lang.t(", duplicates dropped: {0}", len(dropped))
        self.basket.note = note
        self.refresh()
