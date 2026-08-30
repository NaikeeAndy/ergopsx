"""Строки интерфейса. Тот же приём, что в версии для macOS: своя таблица,
а не системная локализация - язык переключается на лету, без перезапуска.
"""

CURRENT = "ru"


def t(ru, en):
    return ru if CURRENT == "ru" else en


def set_language(code):
    global CURRENT
    CURRENT = code if code in ("ru", "en") else "ru"
