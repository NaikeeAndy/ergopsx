#!/usr/bin/env python3
"""Разбор сейва Final Fantasy Tactics.

Смещения - от начала блока сейва (слот занимает ровно один блок, 0x2000).
Источник раскладки: game-tools-collection, шаблон final-fantasy-tactics.
"""

import struct

import psxid

import psxfftdata as data
import psxfftstats as stats

SERIALS = ("SCUS-94221", "SLPS-00770", "SLPM-87392", "SLPS-02768", "SLPS-91435")

# Сводка, которую игра показывает в меню загрузки.
NAME_OFFSET = 0x101
NAME_LENGTH = 0x0E
JOB_PREVIEW = 0x112
LEVEL_PREVIEW = 0x113
PLAYTIME = 0x120

# Общее состояние партии.
WAR_FUNDS = 0x1934
DATE_MONTH = 0x193C
DATE_DAY = 0x1940
LOCATION = 0x1948
BIRTH_MONTH = 0x1A00
BIRTH_DAY = 0x1A04

# Отряд: 20 записей по 0xE0 байт подряд.
UNIT_BASE = 0x484
UNIT_SIZE = 0xE0
UNIT_COUNT = 20
UNIT_TYPE = 0x000          # смещения ниже - от начала записи бойца
UNIT_REGISTERED = 0x001
UNIT_JOB = 0x002
UNIT_GENDER = 0x004        # биты 5..7 - пол, младшие 4 - признак гостя
UNIT_ZODIAC = 0x006
UNIT_STATUS = 0x0D0
UNIT_EXP = 0x015
UNIT_LEVEL = 0x016
UNIT_BRAVE = 0x017
UNIT_FAITH = 0x018
UNIT_NAME = 0x0BE
# Базовые статы: по три байта на каждый, значение делится на 1638400.
# Это не то, что показывает игра, а множитель роста - экранное число
# получается уже с учётом класса и экипировки.
UNIT_STATS = ((0x019, "hp"), (0x01C, "mp"), (0x01F, "sp"),
              (0x022, "pa"), (0x025, "ma"))
# Слоты экипировки. Пустой слот у людей помечен 0xFF; у монстров там 0x00,
# но носить они ничего не могут - индекс 0x00 это Dagger, и его легко принять
# за настоящий предмет (проверено: 0x00 встречается только у монстров).
UNIT_GEAR = ((0x011, "правая рука"), (0x013, "левая рука"), (0x00E, "голова"),
             (0x00F, "тело"), (0x010, "аксессуар"))
GEAR_EMPTY = 0xFF

# Инвентарь: по байту-счётчику на предмет, индекс предмета - смещение от базы.
INVENTORY_BASE = 0x1605

GROWTH = stats.load()
JOB_TABLE = stats.job_table(GROWTH)

NAME_END = 0xFE
# Месяцы в сейве нумеруются с единицы, а не с нуля.
MONTHS = {1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май",
          6: "Июнь", 7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь",
          11: "Ноябрь", 12: "Декабрь"}
ZODIAC = ("Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", "Весы",
          "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы")
# Пол занимает три старших бита байта, а не весь байт.
GENDERS = {4: "мужской", 2: "женский", 1: "монстр"}
STATUSES = {0x0: "", 0x1: "временно покидает отряд"}


def is_fft(frame):
    """Опознаётся по коду игры в каталожном фрейме карты."""
    return psxid.serial_of(frame) in SERIALS


def decode_name(raw):
    """Своя кодировка на 271 символ, конец строки - 0xFE."""
    out = []
    for byte in raw:
        if byte == NAME_END:
            break
        out.append(data.LETTERS.get(byte, "?"))
    return "".join(out).strip()


def _job_name(value, gender):
    if gender == 1:
        return data.MONSTERS.get(value, data.JOBS.get(value, f"#{value}"))
    return data.JOBS.get(value, data.MONSTERS.get(value, f"#{value}"))


def units(block):
    out = []
    for index in range(UNIT_COUNT):
        base = UNIT_BASE + index * UNIT_SIZE
        kind = block[base + UNIT_TYPE]
        if kind == 0:
            continue
        gender_byte = block[base + UNIT_GENDER]
        gender = (gender_byte >> 5) & 0x7
        # Знак зодиака лежит в старших четырёх битах байта.
        zodiac = block[base + UNIT_ZODIAC] >> 4
        gear = []
        if gender != 1:
            for offset, label in UNIT_GEAR:
                value = block[base + offset]
                if value != GEAR_EMPTY and value in data.ITEMS:
                    gear.append((label, data.ITEMS[value]))

        raw_stats = {key: int.from_bytes(block[base + off:base + off + 3], "little")
                     for off, key in UNIT_STATS}
        job_id = block[base + UNIT_JOB]
        job_data = JOB_TABLE.get(job_id)
        # Классов монстров в справочнике роста нет по существу (класс один,
        # гриндить нечего), но там же не хватает и части гостевых сюжетных -
        # это разные причины, и путать их в выводе нельзя.
        is_monster = gender == 1
        # У монстров класс один и сменить его нельзя, поэтому таблицы множителей
        # для них не существует - экранные статы не посчитать, только raw.
        shown = stats.displayed(raw_stats, job_data, GROWTH) if job_data else {}
        at_cap = stats.capped(raw_stats, GROWTH)

        out.append({
            "slot": index + 1,
            "gear": gear,
            "raw_stats": raw_stats,
            "is_monster": is_monster,
            "job_known": job_data is not None,
            "stats": shown,
            "at_cap": at_cap,
            "name": decode_name(block[base + UNIT_NAME:base + UNIT_NAME + NAME_LENGTH]),
            "who": data.UNIT_TYPES.get(kind, ""),
            "job": _job_name(block[base + UNIT_JOB], gender),
            "level": block[base + UNIT_LEVEL],
            "exp": block[base + UNIT_EXP],
            "brave": block[base + UNIT_BRAVE],
            "faith": block[base + UNIT_FAITH],
            "gender": GENDERS.get(gender, f"?{gender}"),
            "guest": bool(gender_byte & 0x0F),
            "status": STATUSES.get(block[base + UNIT_STATUS], ""),
            "zodiac": ZODIAC[zodiac] if zodiac < len(ZODIAC) else "?",
        })
    return out


def inventory(block):
    out = []
    for index, name in sorted(data.ITEMS.items()):
        count = block[INVENTORY_BASE + index]
        if count:
            out.append((name, count))
    return out


def overview(block, frame=None):
    if frame is not None and not is_fft(frame):
        return None
    if len(block) < 0x2000:
        return None
    seconds = struct.unpack_from("<I", block, PLAYTIME)[0]
    month = struct.unpack_from("<I", block, DATE_MONTH)[0]
    birth_month = struct.unpack_from("<I", block, BIRTH_MONTH)[0]
    return {
        "name": decode_name(block[NAME_OFFSET:NAME_OFFSET + NAME_LENGTH]),
        "playtime": (seconds // 3600, seconds // 60 % 60, seconds % 60),
        "playtime_raw": seconds,
        "level": block[LEVEL_PREVIEW],
        "job": data.JOBS.get(block[JOB_PREVIEW], f"#{block[JOB_PREVIEW]}"),
        "funds": struct.unpack_from("<I", block, WAR_FUNDS)[0],
        "date": (MONTHS.get(month, f"#{month}"),
                 struct.unpack_from("<I", block, DATE_DAY)[0]),
        "birthday": (MONTHS.get(birth_month, f"#{birth_month}"),
                     struct.unpack_from("<I", block, BIRTH_DAY)[0]),
        "location": data.LOCATIONS.get(block[LOCATION], f"#{block[LOCATION]}"),
        "units": units(block),
        "inventory": inventory(block),
    }


def report(info, indent=""):
    lines = []
    add = lines.append
    hours, minutes, seconds = info["playtime"]
    add(f"{indent}герой: {info['name']}, {info['job']}, уровень {info['level']}")
    add(f"{indent}наиграно: {hours}:{minutes:02d}:{seconds:02d}")
    add(f"{indent}казна: {info['funds']:,} гил".replace(",", " "))
    add(f"{indent}дата в игре: {info['date'][1]} {info['date'][0]}"
        f" · день рождения: {info['birthday'][1]} {info['birthday'][0]}")
    add(f"{indent}место: {info['location']}")

    add("")
    add(f"{indent}Отряд ({len(info['units'])} бойцов)")
    add(f"{indent}  {'имя':<14} {'ур':>3} {'класс':<24} {'храбр':>6} {'вера':>5}  прочее")
    for unit in info["units"]:
        extra = " · ".join(x for x in (
            unit["who"], unit["gender"], unit["zodiac"],
            "гость" if unit["guest"] else "", unit["status"]) if x)
        add(f"{indent}  {unit['name'][:14]:<14} {unit['level']:>3} {unit['job'][:24]:<24}"
            f" {unit['brave']:>6} {unit['faith']:>5}  {extra}")
        if unit["stats"]:
            add(f"{indent}      " + "  ".join(
                f"{stats.STAT_LABELS[k]} {v}" for k, v in unit["stats"].items()))
        else:
            why = ("класс один, экранные не считаются" if unit["is_monster"]
                   else "класса нет в справочнике роста")
            add(f"{indent}      raw: " + "  ".join(
                f"{stats.STAT_LABELS[k]} {v}" for k, v in unit["raw_stats"].items())
                + f"  ({why})")
        if unit["gear"]:
            add(f"{indent}      " + ", ".join(n for _, n in unit["gear"]))

    add("")
    add(f"{indent}Инвентарь ({len(info['inventory'])} позиций)")
    for name, count in info["inventory"]:
        add(f"{indent}  {name:<22} ×{count}")
    return "\n".join(lines)


def worn_items(block):
    """Что надето на бойцах - в общий склад эти предметы не попадают."""
    worn = {}
    for unit in units(block):
        for _, name in unit["gear"]:
            worn.setdefault(name, set()).add(unit["name"])
    return worn


def absent_items(block):
    """Предметы, которых нет ни на складе, ни на бойцах."""
    worn = worn_items(block)
    return sorted(name for index, name in data.ITEMS.items()
                  if block[INVENTORY_BASE + index] == 0 and name not in worn)
