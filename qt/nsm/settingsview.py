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
        self.setWindowTitle(lang.t("Настройки", "Settings"))
        self.resize(620, 460)
        # Без имени правило фона не срабатывает, и окно
        # остаётся белым - текст на нём почти не виден.
        self.setObjectName("root")
        self.setStyleSheet(sheet(palette))

        column = QVBoxLayout(self)
        column.setContentsMargins(20, 18, 20, 18)
        column.setSpacing(12)

        column.addWidget(self._title(lang.t("Папки с сейвами", "Save folders")))
        note = QLabel(lang.t(
            lang.t("Читаются при запуске. Их может быть сколько угодно — коллекция, ", "Read at startup. As many as you like — the collection, ")
            + lang.t("выгрузки с консолей, чужие карты. Приложение только читает.", "console dumps, other people's cards. The app only reads."),
            "Read at startup. As many as you like — the collection, console "
            "dumps, other people's cards. The app only reads."))
        note.setObjectName("dim")
        note.setWordWrap(True)
        column.addWidget(note)

        self.list = QListWidget()
        column.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        add = QPushButton(lang.t("Добавить папку…", "Add folder…"))
        add.setObjectName("primary")
        add.clicked.connect(self._add)
        buttons.addWidget(add)
        drop = QPushButton(lang.t("Убрать из списка", "Remove from list"))
        drop.clicked.connect(self._remove)
        buttons.addWidget(drop)
        buttons.addStretch(1)
        column.addLayout(buttons)

        column.addWidget(self._title(lang.t("Язык", "Language")))
        self.language = QComboBox()
        self.language.addItems(["Русский", "English"])
        self.language.setCurrentIndex(0 if settings.language == "ru" else 1)
        self.language.currentIndexChanged.connect(self._language)
        self.language.setFixedWidth(240)
        column.addWidget(self.language)
        hint = QLabel(lang.t(
            lang.t("Разбор сейвов и названия игр остаются как есть — ", "Save contents and game titles stay as they are — ")
            + lang.t("они приходят из самих игр.", "they come from the games themselves."),
            "Save contents and game titles stay as they are — "
            "they come from the games themselves."))
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
            self, lang.t("Где лежат сейвы", "Where the saves are"))
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
        self.settings.language = "ru" if index == 0 else "en"
        self.settings.save()
        lang.set_language(self.settings.language)
        self.changed.emit()
