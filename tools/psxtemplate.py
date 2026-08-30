#!/usr/bin/env python3
"""Универсальный разбор по декларативным шаблонам game-tools-collection.

Даёт простые поля (число, флаг, значение из справочника) по любой игре, для
которой есть шаблон. Составные разделы - отряды, инвентари, битовые карты -
сюда не попадают: они у каждой игры устроены по-своему, для них пишется
отдельный модуль.

Смещения в шаблонах отсчитываются от начала блока сейва не у всех игр:
у Castlevania это `блок + 0x100`. Поправки лежат в BASES и выяснялись якорем,
а не предположением.
"""

import json
import os
import struct

import psxid

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "templates.json")

# Смещения шаблонов отсчитываются от начала данных игры, а оно зависит от
# числа кадров иконки: psxid.template_base. Раньше тут была таблица поправок
# по играм, но поправка не свойство игры - у Castlevania и Resident Evil
# в коллекции есть сейвы и с одним кадром, и с тремя.

# Игры с отдельным подробным модулем - универсальный разбор для них лишний.
HANDWRITTEN = {"final-fantasy-tactics", "castlevania-symphony-of-the-night",
               "final-fantasy-ix", "resident-evil", "final-fantasy-viii"}

READERS = {
    "uint8": (1, lambda b, o: b[o]),
    "int8": (1, lambda b, o: struct.unpack_from("<b", b, o)[0]),
    "uint16": (2, lambda b, o: struct.unpack_from("<H", b, o)[0]),
    "int16": (2, lambda b, o: struct.unpack_from("<h", b, o)[0]),
    "uint32": (4, lambda b, o: struct.unpack_from("<I", b, o)[0]),
    "int32": (4, lambda b, o: struct.unpack_from("<i", b, o)[0]),
    "lower4": (1, lambda b, o: b[o] & 0x0F),
    "upper4": (1, lambda b, o: b[o] >> 4),
}


def load(path=DATA_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def by_serial(data=None):
    """Серийник -> (имя игры, описание шаблона)."""
    data = data or load()
    out = {}
    for game, spec in data.items():
        for serial in spec["serials"]:
            out[serial] = (game, spec)
    return out


def serial_of(frame):
    return psxid.serial_of(frame)


# Ниже 0x100 у шаблона идут поля заголовка блока - подпись, иконка. Они лежат
# на месте всегда, сдвигать их нельзя: сдвиг относится только к данным игры.
HEADER_LIMIT = 0x100


def read_field(block, field, base):
    offset = field["o"] + (base if field["o"] >= HEADER_LIMIT else 0)
    if field["t"] == "bit":
        if offset >= len(block):
            return None
        return bool((block[offset] >> (field["b"] or 0)) & 1)
    size, reader = READERS[field["t"]]
    if offset + size > len(block):
        return None
    value = reader(block, offset)
    # Часть полей упакована битами внутри числа: у Crash Bandicoot в одном
    # u16 лежат и номер уровня, и число самоцветов. Без этой распаковки оба
    # читались как всё число целиком и совпадали друг с другом.
    if "bs" in field and "bl" in field:
        value = (value >> field["bs"]) & ((1 << field["bl"]) - 1)
    return value


def overview(block, frame, data=None, index=None):
    """Все простые поля игры или None, если шаблона нет."""
    index = index or by_serial(data)
    found = index.get(serial_of(frame))
    if not found:
        return None
    game, spec = found
    if game in HANDWRITTEN:
        return None
    base = psxid.template_base(block)
    # Одно и то же имя встречается по нескольку раз (у SotN "Experience" есть
    # и у героя, и у каждого фамильяра). Одноимённые различаем смещением,
    # иначе в выводе останется случайное последнее.
    counts = {}
    for field in spec["fields"]:
        counts[field["n"]] = counts.get(field["n"], 0) + 1

    sections = []
    for section in spec.get("flags", []):
        # Часть шаблонов адресует всю карту памяти или распакованные данные,
        # и такие флаги за пределами блока. Раздел, дотянуться до которого
        # удалось меньше чем наполовину, не показываем: «0 из 16» там
        # означало бы не «ничего не собрано», а «прочитать нечем».
        reachable = [(offset, bit, label) for offset, bit, label in section["f"]
                     if base + offset < len(block)]
        if len(reachable) * 2 < len(section["f"]):
            continue
        on = [label for offset, bit, label in reachable
              if (block[base + offset] >> bit) & 1]
        if on:
            sections.append({"name": section["n"], "total": len(reachable),
                             "set": on})

    fields = []
    for field in spec["fields"]:
        value = read_field(block, field, base)
        if value is None:
            continue
        shown = value
        if field["r"]:
            table = spec["resources"].get(field["r"])
            if table:
                shown = table.get(str(value), table.get(value, value))
        label = (field["n"] if counts[field["n"]] == 1
                 else f'{field["n"]} @{field["o"]:#x}')
        fields.append({"name": label, "value": shown, "raw": value})
    return {"game": game, "fields": fields, "sections": sections}


def report(info, indent=""):
    lines = [f"{indent}{info['game']} — {len(info['fields'])} полей"]
    for field in info["fields"]:
        lines.append(f"{indent}  {field['name'][:34]:<34} {field['value']}")
    for section in info.get("sections", []):
        lines.append(f"{indent}  {section['name']}: "
                     f"{len(section['set'])} из {section['total']}")
        lines.append(f"{indent}    {', '.join(section['set'])}")
    return "\n".join(lines)
