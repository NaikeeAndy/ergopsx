#!/usr/bin/env python3
"""Разбор сейва Final Fantasy V (издание для PS1 из Final Fantasy Anthology).

Раскладка — из дизассемблировки everything8215/ff5: слот сохранения там
побайтовая копия куска WRAM `$7E:0500-$7E:0AFF`, то есть подробная карта RAM
и есть карта сейва.

**В блоке карты памяти PS1 слот SNES начинается с 0x300**, а не с 0x200, как
у FF6: перед ним лежат ещё 0x100 байт превью для меню загрузки (имена, уровни,
HP, MP, копия времени и денег). Смещения ниже — от начала слота, то есть
от `блок + 0x300`.

Проверено на девяти настоящих сейвах: время и уровень сходятся с подписью,
которую пишет игра, деньги и число сохранений растут согласованно, количества
предметов упираются ровно в 99 — предел FF5.

Названия предметов, работ и заклинаний вытащены из IPS-патча английского
перевода RPGe 1.10 - см. psxff5data. Это формулировки фанатского перевода
SNES-версии; PS1-издание переводили заново, и часть названий там звучит иначе,
но номера общие - движок один.
"""

import struct

import psxid

import psxff5data as data

SERIALS = ("SLUS-00879", "SCES-13840", "SLPS-01340", "SLPM-86140")

SLOT = 0x300               # слот SNES внутри блока PS1
PREVIEW = 0x200            # превью для меню загрузки, своё у PS1-порта

# Смещения внутри слота
UNITS = 0x000              # 4 персонажа по 0x50
UNIT_SIZE = 0x50
UNIT_COUNT = 4
ITEM_IDS = 0x140           # 256 слотов
ITEM_COUNTS = 0x240
JOBS_OPEN = 0x340          # битовая маска доступных работ
JOB_DATA = 0x343           # 4 персонажа × 22 работы × 2 байта
ABILITY_COUNT = 0x3F3      # выучено способностей, по одному байту на бойца
MONEY = 0x447              # 3 байта
PLAYTIME = 0x44A           # u32, кадры 60 Гц
KILLS = 0x44E              # u16
NAMES = 0x490              # 6 записей по 6 байт: Butz, Lenna, Galuf, Faris, Krile
BATTLES = 0x4C0            # u16
SAVE_COUNT = 0x4C2         # u16
CHESTS = 0x4D4             # 32 байта = 256 сундуков
MAP_INDEX = 0x5D4          # u16
WORLD_INDEX = 0x5D6        # u16
PARTY_X = 0x5D8
PARTY_Y = 0x5D9

# Внутри записи персонажа
U_WHO = 0x00               # младшие три бита - номер героя в ростере
U_JOB = 0x01
U_LEVEL = 0x02
U_EXP = 0x03               # 3 байта
U_HP = 0x06                # текущее u16, максимум по +0x08
U_MP = 0x0A                # текущее u16, максимум по +0x0C
U_GEAR = 0x0E              # шлем, броня, аксессуар, щит R, щит L, оружие R, оружие L
U_JOB_LEVEL = 0x3A
U_ABP = 0x3B               # u16

GEAR_SLOTS = ("шлем", "броня", "аксессуар", "щит справа", "щит слева",
              "оружие справа", "оружие слева")
NAME_LENGTH = 6
NAME_END = 0xFF
FRAMES = 60


def is_ff5(frame):
    return psxid.serial_of(frame) in SERIALS


def decode_name(raw):
    out = []
    for byte in raw:
        if byte == NAME_END:
            break
        out.append(data.LETTERS.get(byte, ""))
    return "".join(out).strip()


def _u16(block, offset):
    return struct.unpack_from("<H", block, offset)[0]


def _u24(block, offset):
    return block[offset] | block[offset + 1] << 8 | block[offset + 2] << 16


def playtime(block):
    total = struct.unpack_from("<I", block, SLOT + PLAYTIME)[0] // FRAMES
    return total // 3600, total // 60 % 60, total % 60


def names(block):
    base = SLOT + NAMES
    return [decode_name(block[base + i * NAME_LENGTH:base + (i + 1) * NAME_LENGTH])
            for i in range(6)]


def party(block):
    roster = names(block)
    out = []
    for index in range(UNIT_COUNT):
        base = SLOT + UNITS + index * UNIT_SIZE
        gear = [(slot, item_name(block[base + U_GEAR + n]))
                for n, slot in enumerate(GEAR_SLOTS)
                if block[base + U_GEAR + n]]
        # Порядок записей отряда не совпадает с ростером: кто именно в слоте,
        # говорят младшие три бита флагов. Сверено с превью меню загрузки на
        # обоих прохождениях.
        who = block[base + U_WHO] & 0x07
        out.append({
            "slot": index,
            "who": who,
            "name": roster[who] if who < len(roster) and roster[who] else f"#{who}",
            "job": data.JOBS.get(block[base + U_JOB], f"#{block[base + U_JOB]}"),
            "level": block[base + U_LEVEL],
            "exp": _u24(block, base + U_EXP),
            "hp": (_u16(block, base + U_HP), _u16(block, base + U_HP + 2)),
            "mp": (_u16(block, base + U_MP), _u16(block, base + U_MP + 2)),
            "job_level": block[base + U_JOB_LEVEL],
            "abp": _u16(block, base + U_ABP),
            "gear": gear,
        })
    return out


def item_name(index):
    return data.ITEMS.get(index, f"#{index}")


def inventory(block):
    """[(название, количество)] - параллельные массивы id и счётчиков."""
    ids, counts = SLOT + ITEM_IDS, SLOT + ITEM_COUNTS
    return [(item_name(block[ids + slot]), block[counts + slot])
            for slot in range(256) if block[counts + slot]]


def chests(block):
    """Сколько сундуков открыто - из них игра считает процент прохождения."""
    base = SLOT + CHESTS
    return sum(bin(block[base + byte]).count("1") for byte in range(32))


def overview(block, frame=None):
    if frame is not None and not is_ff5(frame):
        return None
    if len(block) < SLOT + 0x600:
        return None
    return {
        "playtime": playtime(block),
        "money": _u24(block, SLOT + MONEY),
        "party": party(block),
        "roster": [name for name in names(block) if name],
        "inventory": inventory(block),
        "kills": _u16(block, SLOT + KILLS),
        "battles": _u16(block, SLOT + BATTLES),
        "saves": _u16(block, SLOT + SAVE_COUNT),
        "chests": chests(block),
        "map": _u16(block, SLOT + MAP_INDEX),
        "world": _u16(block, SLOT + WORLD_INDEX),
    }


def report(info, indent=""):
    hours, minutes, seconds = info["playtime"]
    lines = [f"{indent}Final Fantasy V — {hours}:{minutes:02d}:{seconds:02d}, "
             f"{info['money']} гил",
             f"{indent}боёв {info['battles']}, убито {info['kills']}, "
             f"сохранений {info['saves']}, сундуков открыто {info['chests']}",
             f"{indent}  {'имя':<8} {'ур':>3} {'работа':<10} {'ABP':>5} "
             f"{'HP':>12} {'MP':>10}"]
    for unit in info["party"]:
        lines.append(f"{indent}  {unit['name'][:8]:<8} {unit['level']:>3} "
                     f"{unit['job'][:10]:<10} {unit['abp']:>5} "
                     f"{unit['hp'][0]:>5}/{unit['hp'][1]:<5} "
                     f"{unit['mp'][0]:>4}/{unit['mp'][1]:<4}")
    total = sum(count for _, count in info["inventory"])
    lines.append(f"{indent}инвентарь: {len(info['inventory'])} позиций, "
                 f"{total} штук")
    for name, count in info["inventory"][:10]:
        lines.append(f"{indent}  {name:<12} ×{count}")
    return "\n".join(lines)


def main():
    import argparse
    import psxchoco
    parser = argparse.ArgumentParser(description="Разбор сейвов Final Fantasy V")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    for path in args.paths:
        for item in psxchoco.scan(path):
            if not is_ff5(item["frame"]):
                continue
            info = overview(item["block"])
            if info:
                print(f"{path} — {item['where']}")
                print(report(info, "  "))
                print()


if __name__ == "__main__":
    main()
