"""Окно консоли: список файлов, просмотр карты без скачивания, забрать к себе."""

import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from . import lang
from .consoles import Console
from .style import sheet
from .theme import Palette


class Job(QThread):
    """Сеть - в стороне от окна, иначе оно подвисает на каждом запросе."""
    done = Signal(object, str)

    def __init__(self, work):
        super().__init__()
        self.work = work

    def run(self):
        try:
            self.done.emit(self.work(), "")
        except Exception as error:
            self.done.emit(None, str(error))


class ConsoleView(QDialog):
    downloaded = Signal()

    def __init__(self, profile, library, collection, palette: Palette,
                 parent=None):
        super().__init__(parent)
        self.console = Console(profile)
        self.library = library
        self.collection = collection
        self.p = palette
        self.job = None
        self.setObjectName("root")
        self.setWindowTitle(lang.t("{0} — console", profile["label"]))
        self.resize(860, 700)
        self.setStyleSheet(sheet(palette))

        column = QVBoxLayout(self)
        column.setContentsMargins(18, 16, 18, 16)
        column.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel(f"{profile['label']}  ·  {profile['host']}:{profile['port']}")
        font = title.font()
        font.setPointSizeF(14)
        font.setBold(True)
        title.setFont(font)
        head.addWidget(title)
        head.addStretch(1)
        self.again = QPushButton(lang.t("Refresh"))
        self.again.clicked.connect(self.reload)
        head.addWidget(self.again)
        column.addLayout(head)

        self.where = QLabel(self.console.path)
        self.where.setObjectName("dim")
        column.addWidget(self.where)

        body = QHBoxLayout()
        self.files = QListWidget()
        self.files.itemDoubleClicked.connect(self._enter)
        self.files.currentItemChanged.connect(self._peek)
        body.addWidget(self.files, 1)

        self.inside = QListWidget()
        self.inside.setFixedWidth(320)
        body.addWidget(self.inside)
        column.addLayout(body, 1)

        buttons = QHBoxLayout()
        self.take = QPushButton(lang.t("Fetch to collection"))
        self.take.setObjectName("primary")
        self.take.clicked.connect(self._download)
        buttons.addWidget(self.take)
        buttons.addStretch(1)
        self.note = QLabel(lang.t("What you write is picked up only when the game starts"))
        self.note.setObjectName("faint")
        buttons.addWidget(self.note)
        column.addLayout(buttons)
        self.reload()

    # --- сеть

    def _run(self, work, then):
        self.again.setEnabled(False)
        self.job = Job(work)
        self.job.done.connect(lambda got, error: self._finish(got, error, then))
        self.job.start()

    def _finish(self, got, error, then):
        self.again.setEnabled(True)
        if error:
            self.note.setText(error[:120])
            return
        then(got)

    def reload(self, path=None):
        target = path or self.console.path
        self.where.setText(target)
        self.files.clear()
        self.files.addItem(lang.t("loading…"))
        self._run(lambda: self.console.listdir(target), self._show)

    def _show(self, rows):
        self.files.clear()
        for name, size, is_dir in rows:
            label = f"{'📁 ' if is_dir else ''}{name}"
            if not is_dir:
                label += lang.t("    {0} KB", size // 1024)
            row = QListWidgetItem(label)
            row.setData(Qt.UserRole, (name, is_dir))
            self.files.addItem(row)

    def _enter(self, row):
        name, is_dir = row.data(Qt.UserRole) or ("", False)
        if is_dir:
            self.reload(self.console.path.rstrip("/") + "/" + name)

    def _peek(self, current, _previous):
        """Смотрим содержимое, не сохраняя: карта читается в память."""
        self.inside.clear()
        if current is None:
            return
        got = current.data(Qt.UserRole)
        if not got or got[1]:
            return
        name = got[0]
        self._run(lambda: self.console.fetch(name), self._show_inside)

    def _show_inside(self, payload):
        import psxbuild
        import psxid
        self.inside.clear()
        try:
            entries = psxbuild.sources_from_bytes(payload) \
                if hasattr(psxbuild, "sources_from_bytes") else None
        except Exception:
            entries = None
        if entries is None:
            # У psxbuild нет чтения из памяти - кладём во временный файл.
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as fh:
                fh.write(payload)
                temp = fh.name
            try:
                entries = psxbuild.sources(temp)
            except Exception:
                entries = []
            finally:
                os.unlink(temp)
        for entry in entries or []:
            frame = bytearray(psxid.FRAME)
            frame[10:30] = bytes(entry["name"])
            body = b"".join(entry["blocks"])
            found = psxid.describe(bytes(frame), body, self.library.titles)
            self.inside.addItem(
                f"{found['title'] or found['serial']} — {found['internal']}")
        if not entries:
            self.inside.addItem(lang.t("neither a save nor a card image"))

    def _download(self):
        current = self.files.currentItem()
        if current is None or not self.collection:
            return
        got = current.data(Qt.UserRole)
        if not got or got[1]:
            return
        name = got[0]
        self._run(lambda: self.console.download(name, self.collection),
                  self._saved)

    def _saved(self, path):
        self.note.setText(lang.t("saved: {0}", os.path.basename(path)))
        self.downloaded.emit()
