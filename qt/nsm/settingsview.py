"""Окно настроек: папки с сейвами и язык."""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

from . import lang
from .style import sheet
from .theme import Palette


class SettingsView(QDialog):
    changed = Signal()

    def __init__(self, settings, palette: Palette, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.p = palette
        self.setWindowTitle(lang.t("Settings"))
        self.resize(620, 460)
        # Без имени правило фона не срабатывает, и окно
        # остаётся белым - текст на нём почти не виден.
        self.setObjectName("root")
        self.setStyleSheet(sheet(palette))

        column = QVBoxLayout(self)
        column.setContentsMargins(20, 18, 20, 18)
        column.setSpacing(12)

        column.addWidget(self._title(lang.t("Save folders")))
        note = QLabel(lang.t("Read at startup. As many as you like — the collection, console dumps, other people's cards. The app only reads."))
        note.setObjectName("dim")
        note.setWordWrap(True)
        column.addWidget(note)

        self.list = QListWidget()
        column.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        add = QPushButton(lang.t("Add folder…"))
        add.setObjectName("primary")
        add.clicked.connect(self._add)
        buttons.addWidget(add)
        drop = QPushButton(lang.t("Remove from list"))
        drop.clicked.connect(self._remove)
        buttons.addWidget(drop)
        buttons.addStretch(1)
        column.addLayout(buttons)

        column.addWidget(self._title(lang.t("Language")))
        self.language = QComboBox()
        self.language.addItems([name for _, name in lang.LANGUAGES])
        codes = [code for code, _ in lang.LANGUAGES]
        self.language.setCurrentIndex(codes.index(settings.language)
                                      if settings.language in codes else 0)
        self.language.currentIndexChanged.connect(self._language)
        self.language.setFixedWidth(240)
        column.addWidget(self.language)
        hint = QLabel(lang.t("Save contents and game titles stay as they are — they come from the games themselves."))
        hint.setObjectName("faint")
        hint.setWordWrap(True)
        column.addWidget(hint)
        self._fill()

    def _title(self, text):
        made = QLabel(text)
        font = made.font()
        font.setPointSizeF(14)
        font.setBold(True)
        made.setFont(font)
        return made

    def _fill(self):
        self.list.clear()
        for folder in self.settings.folders:
            row = QListWidgetItem(folder)
            row.setToolTip(folder)
            self.list.addItem(row)

    def _add(self):
        folder = QFileDialog.getExistingDirectory(
            self, lang.t("Where the saves are"))
        if folder:
            self.settings.add_folder(folder)
            self._fill()
            self.changed.emit()

    def _remove(self):
        row = self.list.currentItem()
        if row is None:
            return
        # Убираем путь из списка приложения. На диске папка остаётся.
        self.settings.folders = [f for f in self.settings.folders
                                 if f != row.text()]
        self.settings.save()
        self._fill()
        self.changed.emit()

    def _language(self, index):
        self.settings.language = lang.LANGUAGES[index][0]
        self.settings.save()
        lang.set_language(self.settings.language)
        self.changed.emit()
