"""Главное окно: список игр слева, сейвы посередине, разбор справа."""

import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QPushButton, QVBoxLayout, QWidget)

from .basket import Basket
from .basketbar import BasketBar
from .inspector import Inspector
from .library import Library
from .savelist import SaveList
from .sidebar import Sidebar
from .compare import CompareView
from .consoles import profiles
from .consoleview import ConsoleView
from .settings import Settings
from .settingsview import SettingsView
from .style import sheet
from .theme import DARK, LIGHT


class Loader(QThread):
    """Чтение коллекции в стороне от окна, чтобы оно не подвисало."""
    step = Signal(int, int)
    done = Signal()

    def __init__(self, library, folders):
        super().__init__()
        self.library = library
        self.folders = folders

    def run(self):
        self.library.load(self.folders, progress=lambda a, b: self.step.emit(a, b))
        self.done.emit()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.palette_now = DARK if self.settings.dark else LIGHT
        self.library = Library()
        self.basket = Basket()
        self.selection = "*"
        self.loader = None

        self.setWindowTitle("Naikee's Save Manager")
        self.resize(1280, 820)
        self._build()
        self.setStyleSheet(sheet(self.palette_now))
        self.rescan()

    # --- сборка окна

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        column = QVBoxLayout(root)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        column.addWidget(self._bar())
        body = QWidget()
        line = QHBoxLayout(body)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)

        self.sidebar = Sidebar(self.palette_now)
        self.sidebar.setObjectName("panel")
        self.sidebar.setFixedWidth(214)
        self.sidebar.picked.connect(self._pick_game)
        line.addWidget(self.sidebar)
        line.addWidget(self._divider())

        self.list = SaveList(self.palette_now)
        self.list.setFixedWidth(356)
        self.list.chosen.connect(self._pick_save)
        line.addWidget(self.list)
        line.addWidget(self._divider())

        self.inspector = Inspector(self.library, self.palette_now)
        line.addWidget(self.inspector, 1)

        column.addWidget(body, 1)
        self.basket_bar = BasketBar(self.basket, self.palette_now)
        column.addWidget(self.basket_bar)
        self.setCentralWidget(root)
        self.status = self.statusBar()
        self._menus()

    def _menus(self):
        bar = self.menuBar()
        files = bar.addMenu("Файл")
        files.addAction("Обновить список", self.rescan).setShortcut("Ctrl+R")
        files.addAction("Добавить папку…", self.add_folder).setShortcut("Ctrl+O")
        files.addSeparator()
        files.addAction("Собрать карту из корзины…",
                        self.basket_bar._save).setShortcut("Ctrl+Shift+S")
        files.addSeparator()
        files.addAction("Настройки…", self.open_settings).setShortcut("Ctrl+,")

        consoles = bar.addMenu("Консоли")
        found = profiles()
        if not found:
            consoles.addAction("Не настроены").setEnabled(False)
        for profile in found:
            consoles.addAction(
                profile["label"],
                lambda checked=False, p=profile: self.open_console(p))

        saves = bar.addMenu("Сейв")
        saves.addAction("В корзину", self._toggle_basket).setShortcut("Ctrl+D")
        saves.addAction("Сравнить два выделенных",
                        self.compare).setShortcut("Ctrl+=")

    def open_settings(self):
        window = SettingsView(self.settings, self.palette_now, self)
        window.changed.connect(self.rescan)
        window.exec()

    def open_console(self, profile):
        folder = self.settings.folders[0] if self.settings.folders else None
        window = ConsoleView(profile, self.library, folder,
                             self.palette_now, self)
        window.downloaded.connect(self.rescan)
        window.show()

    def compare(self):
        rows = self.list.selected()
        if len(rows) != 2:
            self.status.showMessage(
                "Выделите два сейва: щёлкните второй с Command", 5000)
            return
        CompareView(rows[0], rows[1], self.library, self.palette_now,
                    self).exec()

    def _bar(self):
        bar = QWidget()
        bar.setObjectName("bar")
        bar.setFixedHeight(56)
        line = QHBoxLayout(bar)
        line.setContentsMargins(16, 0, 16, 0)
        line.setSpacing(12)

        self.order = QComboBox()
        self.order.addItems(["По времени", "По названию", "Как в файлах"])
        self.order.currentIndexChanged.connect(lambda _: self.refresh())
        line.addWidget(self.order)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по игре или подписи")
        self.search.setFixedWidth(320)
        self.search.textChanged.connect(lambda _: self.refresh())
        line.addWidget(self.search)

        line.addStretch(1)
        to_basket = QPushButton("В корзину")
        to_basket.setObjectName("primary")
        to_basket.clicked.connect(self._toggle_basket)
        line.addWidget(to_basket)
        add = QPushButton("Добавить папку…")
        add.clicked.connect(self.add_folder)
        line.addWidget(add)
        again = QPushButton("Обновить")
        again.clicked.connect(self.rescan)
        line.addWidget(again)
        return bar

    def _divider(self):
        line = QFrame()
        line.setObjectName("divider")
        line.setFixedWidth(1)
        return line

    # --- данные

    def rescan(self):
        folders = self.settings.folders
        if not folders:
            self.status.showMessage("Папок с сейвами не добавлено")
            return
        self.status.showMessage("Читаю сейвы…")
        self.loader = Loader(self.library, folders)
        self.loader.step.connect(
            lambda done, total: self.status.showMessage(
                f"Читаю сейвы… {done} из {total}"))
        self.loader.done.connect(self._loaded)
        self.loader.start()

    def _loaded(self):
        self.sidebar.fill(self.library)
        self.status.showMessage(
            f"{len(self.library.unique)} сейвов · {len(self.library.games)} игр"
            f" · {self.library.cards} образов карт", 8000)
        self.refresh()

    def refresh(self):
        order = ("playtime", "title", "natural")[self.order.currentIndex()]
        rows = self.library.visible(self.selection, order, self.search.text())
        self.list.show_items(rows)
        # Подталкиваем панель сами: сигнал не приходит, если строка
        # осталась первой, и справа висел бы разбор от прошлой игры.
        current = self.list.currentItem()
        self.inspector.show_item(current.data(Qt.UserRole) if current else None)

    def _pick_game(self, target):
        self.selection = target
        self.refresh()

    def _pick_save(self, item):
        self.current = item
        self.inspector.show_item(item)

    def _toggle_basket(self):
        item = getattr(self, "current", None)
        if item is None:
            item = (self.list.currentItem().data(Qt.UserRole)
                    if self.list.currentItem() else None)
        if item is not None:
            self.basket.toggle(item)
            self.basket_bar.refresh()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Где лежат сейвы")
        if folder:
            self.settings.add_folder(folder)
            self.rescan()
