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
    return os.path.join(base, "ErgoPSX", "config.json")


def _moved_from_old_place(target):
    """Раньше папка звалась по прежнему имени программы.

    Переносим один раз и молча: у того, кто пользовался старой сборкой,
    там лежат папки коллекции, язык и профили консолей.
    """
    old = os.path.join(os.path.dirname(os.path.dirname(target)),
                       os.path.basename(os.path.dirname(target)))
    legacy = os.path.join(os.path.dirname(os.path.dirname(target)),
                          "MemCardSaver")
    if os.path.exists(target) or not os.path.isdir(legacy):
        return
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        for name in os.listdir(legacy):
            os.replace(os.path.join(legacy, name),
                       os.path.join(os.path.dirname(target), name))
        os.rmdir(legacy)
    except OSError:
        pass


class Settings:
    def __init__(self):
        self.path = config_path()
        _moved_from_old_place(self.path)
        self.folders = []
        # "dark" и "light" - наши палитры, "system" - цвета темы
        # операционной системы. Третий вариант нужен на Linux, где у
        # рабочего стола единая тема на все программы.
        self.theme = "dark"
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
        theme = data.get("theme")
        if theme not in ("dark", "light", "system"):
            # Раньше здесь лежал признак `dark`; переносим молча.
            theme = "dark" if data.get("dark", True) else "light"
        self.theme = theme

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"folders": self.folders, "language": self.language,
                       "theme": self.theme}, fh, ensure_ascii=False, indent=1)

    def add_folder(self, folder):
        if folder not in self.folders:
            self.folders.append(folder)
            self.save()
