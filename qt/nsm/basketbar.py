"""Полоса корзины внизу окна: пятнадцать слотов карты и две кнопки.

Всегда на виду, а не отдельным режимом: карта почти всегда собирается из
разных мест сразу, и отдельным экраном пришлось бы всё искать заново.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from .basket import SLOTS, blocks_word, saves_word
from .theme import Palette


class Cells(QWidget):
    """Пятнадцать слотов карты. Занятые подсвечены, продолжение - бледнее."""

    def __init__(self, basket, palette: Palette, parent=None):
        super().__init__(parent)
        self.basket = basket
        self.p = palette
        self.setFixedSize(SLOTS * 26 - 4, 44)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for index, (item, tail) in enumerate(self.basket.layout()):
            box = (index * 26, 2, 22, 40)
            painter.setPen(QColor(self.p.tile_edge))
            if item is None:
                painter.setBrush(QColor(self.p.well))
            else:
                colour = QColor(self.p.accent)
                if tail:
                    colour.setAlpha(110)
                painter.setBrush(colour)
            painter.drawRoundedRect(*box, 5, 5)


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

        title = QLabel("КАРТА")
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

        self.clear_button = QPushButton("Очистить")
        self.clear_button.clicked.connect(self._clear)
        line.addWidget(self.clear_button)

        self.save_button = QPushButton("В файл")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self._save)
        line.addWidget(self.save_button)
        self.refresh()

    def refresh(self):
        empty = not self.basket.items
        self.line1.setText(
            self.basket.note or
            ("Пусто — добавляйте сейвы по дороге, из любого места" if empty
             else f"{len(self.basket.items)} {saves_word(len(self.basket.items))}"))
        self.line2.setText(
            f"занято {self.basket.used} из {SLOTS} блоков")
        self.clear_button.setEnabled(not empty)
        self.save_button.setEnabled(not empty)
        self.cells.update()
        self.changed.emit()

    def _clear(self):
        self.basket.clear()
        self.refresh()

    def _save(self):
        target, _ = QFileDialog.getSaveFileName(
            self, "Собранная карта — исходные файлы не меняются",
            "card.mcr", "Образ карты (*.mcr *.mcd *.VM1)")
        if not target:
            return
        try:
            image, layout, dropped = self.basket.build()
        except Exception as error:
            QMessageBox.warning(self, "Не собралось", str(error))
            return
        with open(target, "wb") as fh:
            fh.write(image)
        note = f"Собрано: {len(layout)} сейвов"
        if dropped:
            note += f", отброшено дублей: {len(dropped)}"
        self.basket.note = note
        self.refresh()
