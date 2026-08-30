#!/usr/bin/env python3
"""Разбор сейва Final Fantasy VI (издание для PS1 из Final Fantasy Anthology).

Шаблона для PS1 не существует - есть только для SNES. Но PS1-порт хранит
сейв SNES дословно, со смещением 0x200 от начала блока: проверено по подписи,
которую пишет сама игра (время сошлось), по осмысленности гилов, шагов
и по отряду, который читается как Terra/Locke/Cyan/Shadow/Edgar/Sabin.

Отличие от SNES одно: таблица букв сдвинута на -0x60.

Смещения - от начала слота SNES, то есть от `блок + 0x200`.
"""

import struct

import psxid

import psxff6data as data

# Валидатор шаблона перечисляет только SNES и GBA, поэтому серийники PS1
# взяты из базы названий. Проверено на американском издании; японские
# используют свою таблицу букв (кана), она сюда не заведена - сверять не на чем.
SERIALS = ("SLUS-00900", "SCES-03828", "SCPS-45387", "SLPM-86198",
           "SLPS-01950")

BASE = 0x200               # слот SNES внутри блока PS1

UNIT = 0x25                # длина записи персонажа
UNITS = 16
MONEY = 0x260              # u24
PLAYTIME = 0x263           # три байта: часы, минуты, секунды
STEPS = 0x266              # u16
ITEM_IDS = 0x269
ITEM_COUNTS = 0x369
ITEM_SLOTS = 256
ESPERS = 0x469             # битовая карта
MAGIC = 0x46E              # 12 персонажей по 54 заклинания
MAGIC_UNITS = 12           # Гого и Умаро магию не учат, дальше идёт Sword Tech
MAGIC_SPELLS = 54
SAVE_COUNT = 0x7C7
LOCATION = 0x964           # u16, значащих 9 бит

# Внутри записи персонажа
U_NAME = 0x02              # 6 байт
U_LEVEL = 0x08
U_HP = 0x09                # текущее u16, максимум по +0x0B
U_HP_MAX = 0x0B            # 14 бит: старшие два заняты флагами
U_MP = 0x0D
U_MP_MAX = 0x0F
U_EXP = 0x11               # u24
U_ABILITIES = 0x16         # четыре байта
U_VIGOR = 0x1A
U_GEAR = 0x1F              # шесть слотов

GEAR_SLOTS = ("правая рука", "левая рука", "голова", "тело",
              "реликвия 1", "реликвия 2")
STAT_NAMES = ("сила", "скорость", "выносливость", "магия")

EMPTY = 0xFF
LEARNED = 0xFF             # магия выучена; 1..100 - процент изучения


def is_ff6(frame):
    return psxid.serial_of(frame) in SERIALS


def decode_name(raw):
    """Имя персонажа. Таблица та же, что у SNES, но байты сдвинуты на -0x60."""
    out = []
    for byte in raw:
        if byte == EMPTY:
            break
        out.append(data.LETTERS.get(byte + 0x60, ""))
    return "".join(out).strip()


def _u16(block, offset):
    return struct.unpack_from("<H", block, offset)[0]


def _u24(block, offset):
    return block[offset] | block[offset + 1] << 8 | block[offset + 2] << 16


def _item(index):
    return data.ITEMS.get(index, (f"#{index:#04x}", 0))[0]


def _unit(block, index):
    base = BASE + index * UNIT
    name = decode_name(block[base + U_NAME:base + U_NAME + 6])
    if not name:
        return None
    gear = [(slot, _item(block[base + U_GEAR + n]))
            for n, slot in enumerate(GEAR_SLOTS)
            if block[base + U_GEAR + n] != EMPTY]
    abilities = [data.ABILITIES.get(block[base + U_ABILITIES + n], "")
                 for n in range(4)]
    spells = []
    if index < MAGIC_UNITS:
        for spell in range(MAGIC_SPELLS):
            value = block[BASE + MAGIC + index * MAGIC_SPELLS + spell]
            if not value:
                continue
            spells.append({"name": data.MAGIC.get(spell, f"#{spell}"),
                           "learned": value >= 100,
                           "percent": 100 if value >= 100 else value})
    return {
        "slot": index,
        "who": data.CHARACTERS.get(block[base], f"#{block[base]}"),
        "name": name,
        # Не завербованных игра держит в отряде с именем из одних знаков
        # вопроса - это её собственная заглушка, а не сбой чтения.
        "recruited": set(name) != {"?"},
        "level": block[base + U_LEVEL],
        "exp": _u24(block, base + U_EXP),
        # Максимум HP и MP - четырнадцатибитные: старшие два бита заняты
        # флагами снаряжения, без маски выходит 49836 вместо 684.
        # Текущее HP бывает больше сохранённого максимума: в максимуме лежит
        # база, а прибавку от реликвий игра считает на лету.
        "hp": (_u16(block, base + U_HP), _u16(block, base + U_HP_MAX) & 0x3FFF),
        "mp": (_u16(block, base + U_MP), _u16(block, base + U_MP_MAX) & 0x3FFF),
        "stats": tuple(block[base + U_VIGOR + n] for n in range(4)),
        "abilities": [a for a in abilities if a and a != "-"],
        "gear": gear,
        "magic": spells,
    }


def inventory(block):
    out = []
    for slot in range(ITEM_SLOTS):
        index = block[BASE + ITEM_IDS + slot]
        count = block[BASE + ITEM_COUNTS + slot]
        if index == EMPTY or not count:
            continue
        out.append((_item(index), count))
    return out


def espers(block):
    return [data.ESPERS[index] for index in sorted(data.ESPERS)
            if (block[BASE + ESPERS + index // 8] >> (index % 8)) & 1]


def overview(block, frame=None):
    if frame is not None and not is_ff6(frame):
        return None
    if len(block) < BASE + 0xA00:
        return None
    hours, minutes, seconds = (block[BASE + PLAYTIME], block[BASE + PLAYTIME + 1],
                               block[BASE + PLAYTIME + 2])
    location = _u16(block, BASE + LOCATION) & 0x1FF
    party = [unit for unit in (_unit(block, i) for i in range(UNITS)) if unit]
    return {
        "playtime": (hours, minutes, seconds),
        "gil": _u24(block, BASE + MONEY),
        "steps": _u16(block, BASE + STEPS),
        "saves": block[BASE + SAVE_COUNT],
        "location": data.LOCATIONS.get(location, f"#{location}"),
        "party": [unit for unit in party if unit["recruited"]],
        "not_recruited": sum(1 for unit in party if not unit["recruited"]),
        "inventory": inventory(block),
        "espers": espers(block),
    }


def report(info, indent=""):
    hours, minutes, seconds = info["playtime"]
    lines = [f"{indent}Final Fantasy VI — {hours}:{minutes:02d}:{seconds:02d}, "
             f"{info['gil']} гилов, {info['location']}",
             f"{indent}шагов {info['steps']}, сохранений {info['saves']}",
             f"{indent}эсперы ({len(info['espers'])}): "
             f"{', '.join(info['espers']) or '—'}"]
    lines.append(f"{indent}  {'имя':<8} {'ур':>3} {'HP':>10} {'MP':>9} "
                 f"{'магия':>6}  экипировка")
    for unit in info["party"]:
        hp = f"{unit['hp'][0]}/{unit['hp'][1]}"
        mp = f"{unit['mp'][0]}/{unit['mp'][1]}"
        learned = sum(1 for spell in unit["magic"] if spell["learned"])
        gear = ", ".join(name for _, name in unit["gear"]) or "—"
        lines.append(f"{indent}  {unit['name'][:8]:<8} {unit['level']:>3} "
                     f"{hp:>10} {mp:>9} {learned:>6}  {gear[:40]}")
    if info["not_recruited"]:
        lines.append(f"{indent}ещё не завербовано: {info['not_recruited']}")
    lines.append(f"{indent}инвентарь — {len(info['inventory'])} позиций")
    for name, count in info["inventory"][:12]:
        lines.append(f"{indent}  {name:<20} ×{count}")
    return "\n".join(lines)


def main():
    import argparse
    import psxchoco
    parser = argparse.ArgumentParser(description="Разбор сейвов Final Fantasy VI")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    for path in args.paths:
        for item in psxchoco.scan(path):
            if not is_ff6(item["frame"]):
                continue
            info = overview(item["block"])
            if info:
                print(f"{path} — {item['where']}")
                print(report(info, "  "))
                print()


if __name__ == "__main__":
    main()
