"""Консоли по FTP: обход, просмотр карт без скачивания, загрузка к себе.

Клиент - `ftplib` из стандартной библиотеки через `tools/psxftp.py`:
там уже учтено всё, на чём спотыкались прошивки. Главное - webMAN
дописывает в ответ температуру консоли, и разбор канала как UTF-8 на
этом падает; лечится чтением в latin-1.
"""

import io
import os
import sys
from ftplib import FTP

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(HERE, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import psxftp   # noqa: E402
import psxid    # noqa: E402


def profiles(near=None):
    """Профили консолей из общего с остальными инструментами файла."""
    import json
    path = os.path.join(TOOLS, "data", "consoles.json")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for label, entry in sorted(raw.items()):
        out.append({
            "label": label,
            "kind": entry.get("kind", "ps3"),
            "host": entry.get("host", ""),
            "port": int(entry.get("port", 21)),
            "user": entry.get("user", "anonymous"),
            "password": entry.get("password", ""),
            "path": entry.get("path", "/"),
        })
    return out


class Console:
    def __init__(self, profile):
        self.profile = profile
        self.path = profile["path"]

    def _open(self):
        ftp = FTP()
        # latin-1 переносит любые байты без потерь.
        ftp.encoding = "latin-1"
        ftp.connect(self.profile["host"], self.profile["port"], timeout=25)
        ftp.login(self.profile["user"], self.profile["password"])
        return ftp

    def listdir(self, path=None):
        target = path or self.path
        ftp = self._open()
        try:
            rows = psxftp.listdir(ftp, target)
        finally:
            try:
                ftp.quit()
            except Exception:
                pass
        self.path = target
        # Папки первыми, дальше по алфавиту - как в окне на маке.
        return sorted(rows, key=lambda row: (not row[2], row[0].lower()))

    def fetch(self, name):
        """Читает файл в память. На диск ничего не пишется."""
        remote = self.path.rstrip("/") + "/" + name
        ftp = self._open()
        chunks = []
        try:
            ftp.retrbinary(f"RETR {remote}", chunks.append)
        finally:
            try:
                ftp.quit()
            except Exception:
                pass
        return b"".join(chunks)

    def download(self, name, folder):
        """Скачивает в коллекцию. Одноимённое не перезаписываем."""
        payload = self.fetch(name)
        target = os.path.join(folder, "_с консоли", self.profile["label"])
        os.makedirs(target, exist_ok=True)
        path = os.path.join(target, name)
        stem, ext = os.path.splitext(name)
        attempt = 2
        while os.path.exists(path):
            path = os.path.join(target, f"{stem} ({attempt}){ext}")
            attempt += 1
        with open(path, "wb") as fh:
            fh.write(payload)
        return path
