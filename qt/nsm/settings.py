"""Настройки в файле рядом с настройками системы - как у версии для macOS."""

import json
import os
import sys


def config_path():
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME",
                              os.path.expanduser("~/.config"))
    return os.path.join(base, "MemCardSaver", "config.json")


class Settings:
    def __init__(self):
        self.path = config_path()
        self.folders = []
        self.dark = True
        self.language = "en"
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        self.folders = [f for f in data.get("folders", []) if os.path.isdir(f)]
        self.language = data.get("language", "en")
        self.dark = data.get("dark", True)

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"folders": self.folders, "language": self.language,
                       "dark": self.dark}, fh, ensure_ascii=False, indent=1)

    def add_folder(self, folder):
        if folder not in self.folders:
            self.folders.append(folder)
            self.save()
