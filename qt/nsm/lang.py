"""Строки интерфейса.

**Ключ - английская строка.** Английский здесь исходный: он написан прямо
в коде, остальные языки лежат таблицами в `tools/data/i18n`. Нет перевода -
показывается ключ, то есть английский, а не пустое место.

Таблицы общие с версией для macOS: там те же файлы лежат ресурсом внутри
приложения. Своя таблица, а не `gettext`, - чтобы язык переключался на
лету и не требовал сборки `.mo`.
"""

import json
import os

LANGUAGES = [("en", "English"), ("ru", "Русский"), ("fr", "Français"),
             ("de", "Deutsch"), ("ja", "日本語"), ("zh", "中文"),
             ("pl", "Polski")]

CODES = [code for code, _ in LANGUAGES]

CURRENT = "en"
_WORDS = {}
_PLURALS = {}

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Собранное приложение раскладывает `tools/data` ещё и рядом с собой.
DIRS = [os.path.join(HERE, "tools", "data", "i18n"),
        os.path.join(HERE, "data", "i18n"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "i18n")]


def _load(code):
    for base in DIRS:
        path = os.path.join(base, code + ".json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
    return {}


def set_language(code):
    global CURRENT, _WORDS, _PLURALS
    CURRENT = code if code in CODES else "en"
    raw = _load(CURRENT)
    _WORDS = {k: v for k, v in raw.items() if isinstance(v, str)}
    _PLURALS = {k[len("plural:"):]: v for k, v in raw.items()
                if k.startswith("plural:") and isinstance(v, dict)}


def t(key, *args):
    """Строка по ключу. Аргументы подставляются вместо `{0}`, `{1}` и так
    далее - порядок в переводе может быть любым."""
    text = _WORDS.get(key)
    if text is None:
        # Одинаковые английские слова с разным смыслом различаются пометкой
        # после `@@`: «Save@@verb» - кнопка, «Save» - сейв. Наружу она не идёт.
        text = key.split("@@")[0]
    if args:
        text = text.format(*args)
    elif "{{" in text or "}}" in text:
        text = text.replace("{{", "{").replace("}}", "}")
    return text


def plural(noun, count):
    """Слово при числе. Форму выбирает язык, а не место вызова: у русского
    и польского их три, у французского и немецкого две, у японского и
    китайского одна."""
    forms = _PLURALS.get(noun)
    if not forms:
        return noun
    return forms.get(_form(CURRENT, count)) or forms.get("other") or noun


def _form(code, count):
    if code in ("ja", "zh"):
        return "other"
    if code in ("ru", "pl"):
        ten, hundred = count % 10, count % 100
        if ten == 1 and hundred != 11:
            return "one"
        if 2 <= ten <= 4 and not 12 <= hundred <= 14:
            return "few"
        return "many"
    if code == "fr":
        return "one" if count < 2 else "other"
    return "one" if count == 1 else "other"


set_language(CURRENT)
