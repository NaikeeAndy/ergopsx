#!/usr/bin/env python3
"""Перегон таблиц названий в JSON - ресурс, общий для обоих движков.

Таблицы (`psxff7data` и соседние) занимают около 4300 строк из 10 600 и
логики не содержат вовсе. Переписывать их на Swift незачем: выгружаем один
раз, дальше оба движка читают один и тот же файл, и сверять там нечего.

    python3 tools/psxexport.py
"""

import importlib
import psxid
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEST = "swift/Sources/MemCardKit/Resources"

MODULES = ("psxff9data", "psxff8data", "psxff7data", "psxfftdata",
           "psxff6data", "psxff5data", "psxsotndata", "psxre1data",
           # Не таблица названий, но выгружается по той же причине: таблицу
           # CRC у FF8 нельзя переписывать руками - элемент 255 нулевой, и
           # ошибка в одном числе тихо ломает все суммы.
           "psxff8")

# Готовые JSON из tools/data копируем как есть: они уже в нужном виде,
# и переписывать там нечего.
PLAIN = ("fft-growth.json", "templates.json", "playtime.json",
         "vagrant-map.json")


def plain(value):
    """Ключи словарей в JSON обязаны быть строками."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def export(module_name):
    module = importlib.import_module(module_name)
    tables = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        value = getattr(module, name)
        # Отдельные числа тоже нужны: GF_LEVEL_DIVISOR_DEFAULT у FF8.
        if isinstance(value, (dict, list, tuple)) and value:
            tables[name] = plain(value)
        elif isinstance(value, (int, float, str)) and not callable(value):
            tables[name] = value
    if not tables:
        return None
    os.makedirs(DEST, exist_ok=True)
    path = os.path.join(DEST, f"{module_name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(tables, fh, ensure_ascii=False, sort_keys=True, indent=1)
    return path, tables


def export_titles():
    """База названий - ресурсом внутрь приложения.

    Приложение, запущенное двойным щелчком, работает из корня диска и
    рядом с собой репозиторий не найдёт. Без этого сейвы показываются
    без названий игр."""
    path = psxid.default_titles_path()
    if not os.path.exists(path):
        print("  база названий: не нашлась, пропущена")
        return
    titles = psxid.load_titles(path)
    os.makedirs(DEST, exist_ok=True)
    # Два места по той же причине, что и у таблиц строк: приложению для
    # macOS - ресурсом внутрь, версии на Qt - рядом с движком, откуда
    # упаковщик кладёт её в сборку.
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(DEST, "titles.json")
    for where in (target, os.path.join(here, "data", "titles.json")):
        with open(where, "w", encoding="utf-8") as fh:
            json.dump(titles, fh, ensure_ascii=False, sort_keys=True)
    print(f"  titles.json          {len(titles)} названий, "
          f"{os.path.getsize(target)/1024:.0f} КБ")


def copy_plain():
    import shutil
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(DEST, exist_ok=True)
    for name in PLAIN:
        source = os.path.join(here, "data", name)
        if not os.path.exists(source):
            print(f"  {name}: нет такого файла, пропущен")
            continue
        shutil.copy2(source, os.path.join(DEST, name))
        print(f"  {name:<20} скопирован, {os.path.getsize(source)/1024:.1f} КБ")


def copy_languages():
    """Таблицы строк общие у обоих приложений: Qt читает их из `tools/data`,
    приложению для macOS они кладутся ресурсом внутрь."""
    import shutil
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, "data", "i18n")
    if not os.path.isdir(source):
        print("  i18n: папки нет, пропущено")
        return
    target = os.path.join(DEST, "i18n")
    os.makedirs(target, exist_ok=True)
    tables = {}
    for name in sorted(os.listdir(source)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(source, name), encoding="utf-8") as fh:
            tables[name[:-5]] = json.load(fh)
    check_languages(tables)
    for code, table in sorted(tables.items()):
        shutil.copy2(os.path.join(source, code + ".json"),
                     os.path.join(target, code + ".json"))
        print(f"  i18n/{code + '.json':<15} {len(table)} строк")


def check_languages(tables):
    """Каталоги должны совпадать по ключам и по числу подстановок.

    Ошибка тут тихая: пропущенный ключ просто показывается по-английски,
    а разъехавшиеся `{0}` роняют форматирование уже у пользователя.
    Английский - исходный язык, у него в таблице только формы числа.
    """
    import re
    base = tables.get("ru")
    if not base:
        return
    holes = 0
    for code, table in sorted(tables.items()):
        if code == "en":
            continue
        missing = sorted(k for k in base if k not in table)
        extra = sorted(k for k in table if k not in base)
        for key in missing:
            print(f"  i18n/{code}: нет перевода {key!r}"); holes += 1
        for key in extra:
            print(f"  i18n/{code}: лишний ключ {key!r}"); holes += 1
        for key, value in table.items():
            if not isinstance(value, str):
                continue
            if set(re.findall(r"\{(\d+)\}", key)) != set(re.findall(r"\{(\d+)\}", value)):
                print(f"  i18n/{code}: подстановки разошлись у {key!r}"); holes += 1
    if holes:
        raise SystemExit(f"каталоги строк расходятся: {holes} мест")


def main():
    total = 0
    for name in MODULES:
        try:
            result = export(name)
        except ModuleNotFoundError:
            print(f"  {name}: нет такого модуля, пропущен")
            continue
        if not result:
            print(f"  {name}: таблиц не нашлось")
            continue
        path, tables = result
        size = os.path.getsize(path)
        entries = sum(len(v) if hasattr(v, "__len__") else 1 for v in tables.values())
        total += entries
        print(f"  {name:<14} {len(tables):>2} таблиц, {entries:>5} записей, "
              f"{size/1024:>6.1f} КБ -> {path}")
    print(f"всего записей: {total}")
    copy_plain()
    copy_languages()
    export_titles()


if __name__ == "__main__":
    main()
