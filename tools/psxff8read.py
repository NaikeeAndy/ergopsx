#!/usr/bin/env python3
"""Разбор содержимого сейва Final Fantasy VIII.

Смещения - от начала блока сейва, по hyne/src/SaveData.h. MAIN начинается
с 0x1D0, поля внутри перечислены в комментариях структуры MAIN.
"""

import re
import struct
import unicodedata

import psxff8
import psxff8data as data

GF_COUNT = 16
GF_SIZE = 68
GF_BASE = 464

PARTY_COUNT = 8
PERSO_SIZE = 152
PERSO_BASE = 1552

ITEMS_BASE = 3236
ITEMS_ORDER_SIZE = 32          # battle_order[32] идёт перед самим списком
ITEM_SLOTS = 198

MISC1_BASE = 3188
GILS_OFFSET = MISC1_BASE + 24
PARTY_OFFSET = MISC1_BASE

MISC2_BASE = 3664
GAME_TIME_OFFSET = MISC2_BASE  # первое поле структуры

MISC3_BASE = 3808
STEPS_OFFSET = MISC3_BASE + 4
BATTLES_OFFSET = MISC3_BASE + 20
KILLS_OFFSET = MISC3_BASE + 28

MAGIC_SLOTS = 32
STAT_NAMES = ("Сила", "Стойкость", "Магия", "Дух", "Ловкость", "Удача")

DESCRIPTION_OFFSET = 4
DESCRIPTION_SIZE = 92

# Игра пишет в заголовок не больше 99:59 и дальше не растит.
CAP_HOURS = 99
CAP_MINUTES = 59


def _u8(block, offset):
    return block[offset]


def _u16(block, offset):
    return struct.unpack_from("<H", block, offset)[0]


def _u32(block, offset):
    return struct.unpack_from("<I", block, offset)[0]


def description(block):
    """Заголовок, который написала сама игра: 'FF8[01]/32:54'."""
    raw = bytes(block[DESCRIPTION_OFFSET:DESCRIPTION_OFFSET + DESCRIPTION_SIZE])
    raw = raw.split(b"\x00", 1)[0]
    try:
        text = raw.decode("shift_jis")
    except UnicodeDecodeError:
        text = raw.decode("shift_jis", errors="replace")
    return unicodedata.normalize("NFKC", text).strip()


def playtime(block, region=None):
    """Наигранное время.

    В сейве лежит один 32-битный счётчик. Hyne делит его на 60*freq, где
    freq - 50 для PAL и 60 для NTSC, и называет результат часами; но его же
    поле «секунды» ограничено freq-1, то есть считает кадры. Из одного кода
    не следует, тики это или секунды, поэтому считаем оба варианта и сверяем
    с заголовком, который написала сама игра.
    """
    raw = _u32(block, GAME_TIME_OFFSET)
    freq = 50 if region == "Europe" else 60

    as_seconds = {"hours": raw // 3600, "minutes": raw // 60 % 60, "seconds": raw % 60}
    ticks = raw // freq
    as_ticks = {"hours": ticks // 3600, "minutes": ticks // 60 % 60, "seconds": ticks % 60}

    shown = re.search(r"(\d+)\s*:\s*(\d+)", description(block))
    result = {"raw": raw, "freq": freq, "as_seconds": as_seconds, "as_ticks": as_ticks,
              "shown": None, "matches": None, "capped": False}
    if shown:
        result["shown"] = (int(shown.group(1)), int(shown.group(2)))
        # Поле в заголовке двузначное и упирается в 99:59 - это ограничение,
        # а не переполнение: счётчик за ним продолжает расти.
        result["capped"] = result["shown"] == (CAP_HOURS, CAP_MINUTES)
        for name, value in (("as_seconds", as_seconds), ("as_ticks", as_ticks)):
            if result["capped"]:
                if value["hours"] >= CAP_HOURS:
                    result["matches"] = name
                    break
            elif (value["hours"], value["minutes"]) == result["shown"]:
                result["matches"] = name
                break
    return result


def characters(block):
    out = []
    for index in range(PARTY_COUNT):
        base = PERSO_BASE + index * PERSO_SIZE
        exp = _u32(block, base + 4)
        magic = []
        for slot in range(MAGIC_SLOTS):
            packed = _u16(block, base + 16 + slot * 2)
            spell, count = packed & 0xFF, packed >> 8
            if spell and count:
                magic.append((data.MAGICS[spell] if spell < len(data.MAGICS)
                              else f"#{spell}", count))
        weapon = _u8(block, base + 9)
        out.append({
            "name": data.PARTY_ORDER[index],
            "exists": bool(_u8(block, base + 148)),
            "level": min(100, exp // 1000 + 1),
            "exp": exp,
            "hp": _u16(block, base + 0),
            "hp_max": _u16(block, base + 2),
            "weapon": data.WEAPONS[weapon] if weapon < len(data.WEAPONS) else f"#{weapon}",
            "stats": tuple(_u8(block, base + 10 + i) for i in range(6)),
            "magic": magic,
            "kills": _u16(block, base + 144),
            "gfs": _u16(block, base + 88),
        })
    return out


def guardians(block):
    out = []
    for index in range(GF_COUNT):
        base = GF_BASE + index * GF_SIZE
        exp = _u32(block, base + 12)
        divisor = data.GF_LEVEL_DIVISOR.get(index, data.GF_LEVEL_DIVISOR_DEFAULT)

        # Две разные индексации, и это легко перепутать: маска выученного
        # адресуется глобальным номером способности (GfEditor.cpp:268), а массив
        # AP и маска забытого - номером слота в списке этого Гардиана (строка 341).
        forgotten = (block[base + 65] | (block[base + 66] << 8)
                     | (block[base + 67] << 16))
        learned, learning, lost = [], [], []
        for slot, ability in enumerate(data.GF_ABILITY_SLOTS[index]):
            if ability == 0:
                continue
            name = (data.ABILITIES[ability] if ability < len(data.ABILITIES)
                    else f"#{ability}")
            if (block[base + 20 + ability // 8] >> (ability % 8)) & 1:
                learned.append(name)
            elif (forgotten >> slot) & 1:
                lost.append(name)
            else:
                points = block[base + 36 + slot]
                if points:
                    learning.append((name, points, data.ABILITY_AP_COST[ability]))

        out.append({
            "name": data.GF_NAMES[index],
            "exists": bool(_u8(block, base + 17) & 1),
            "level": min(100, exp // divisor + 1),
            "exp": exp,
            "hp": _u16(block, base + 18),
            "learned": learned,
            "learning": learning,
            "forgotten": lost,
            "total_slots": sum(1 for a in data.GF_ABILITY_SLOTS[index] if a),
            "kills": _u16(block, base + 60),
        })
    return out


def items(block):
    base = ITEMS_BASE + ITEMS_ORDER_SIZE
    out = []
    for slot in range(ITEM_SLOTS):
        packed = _u16(block, base + slot * 2)
        item, count = packed & 0xFF, packed >> 8
        if item and count:
            out.append((data.ITEMS[item] if item < len(data.ITEMS) else f"#{item}",
                        count))
    return out


def overview(block, region=None):
    if not psxff8.is_ff8(block):
        return None
    party = [data.PARTY_ORDER[i] for i in block[PARTY_OFFSET:PARTY_OFFSET + 3]
             if i < len(data.PARTY_ORDER)]
    return {
        "description": description(block),
        "playtime": playtime(block, region),
        "gils": _u32(block, GILS_OFFSET),
        "steps": _u32(block, STEPS_OFFSET),
        "battles": _u32(block, BATTLES_OFFSET),
        "party": party,
        "characters": characters(block),
        "guardians": guardians(block),
        "items": items(block),
        "checksum_ok": psxff8.verify(block)[3],
    }


def format_playtime(info):
    """Строка вида '132:41:07 (по счётчику; заголовок игры показывает 99:00)'."""
    chosen = info["matches"] or "as_seconds"
    value = info[chosen]
    text = f"{value['hours']}:{value['minutes']:02d}:{value['seconds']:02d}"
    if info["matches"] is None:
        other = info["as_ticks"] if chosen == "as_seconds" else info["as_seconds"]
        text += f" (или {other['hours']}:{other['minutes']:02d}, трактовка не подтвердилась)"
    if info.get("capped"):
        text += f" — игра показывает {CAP_HOURS}:{CAP_MINUTES}, дальше её счётчик не растит"
    elif info["shown"] and info["shown"][0] != value["hours"]:
        text += f" — игра в заголовке показывает {info['shown'][0]:02d}:{info['shown'][1]:02d}"
    return text


# --- Вывод -------------------------------------------------------------------

def report(info, indent=""):
    lines = []
    add = lines.append
    time = info["playtime"]
    add(f"{indent}наиграно: {format_playtime(time)}")
    add(f"{indent}гилы {info['gils']:,}".replace(",", " ")
        + f" · шагов {info['steps']:,}".replace(",", " ")
        + f" · боёв {info['battles']}")
    if info["party"]:
        add(f"{indent}партия: {', '.join(info['party'])}")
    if not info["checksum_ok"]:
        add(f"{indent}ВНИМАНИЕ: контрольная сумма не сходится")

    add("")
    add(f"{indent}Персонажи")
    for person in info["characters"]:
        if not person["exists"]:
            continue
        add(f"{indent}  {person['name']:<8} ур.{person['level']:<4}"
            f" HP {person['hp']}/{person['hp_max']:<6} {person['weapon']}")
        add(f"{indent}      " + "  ".join(
            f"{n} {v}" for n, v in zip(STAT_NAMES, person["stats"])))
        if person["magic"]:
            add(f"{indent}      магия: " + ", ".join(
                f"{name} ×{count}" for name, count in person["magic"]))

    add("")
    add(f"{indent}Гардианы")
    for gf in info["guardians"]:
        if not gf["exists"]:
            continue
        add(f"{indent}  {gf['name']:<12} ур.{gf['level']:<4} HP {gf['hp']:<6}"
            f" способностей {len(gf['learned'])}/{gf['total_slots']}")
        if gf["learned"]:
            add(f"{indent}      выучено: " + ", ".join(gf["learned"]))
        for name, points, need in gf["learning"]:
            add(f"{indent}      учит {name}: {points}/{need} AP")
        if gf["forgotten"]:
            add(f"{indent}      забыто: " + ", ".join(gf["forgotten"]))

    add("")
    add(f"{indent}Инвентарь ({len(info['items'])} позиций)")
    for name, count in info["items"]:
        add(f"{indent}  {name:<24} ×{count}")
    return "\n".join(lines)


def main():
    import argparse
    import os
    import psxchoco

    parser = argparse.ArgumentParser(description="Что внутри сейва Final Fantasy VIII")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    for path in args.files:
        try:
            blocks = psxchoco.load_blocks(path)
        except ValueError as error:
            print(f"{os.path.basename(path)}: {error}\n")
            continue
        for where, block, _ in blocks:
            info = overview(block)
            if info is None:
                continue
            print(f"{os.path.basename(path)} — {where}")
            print(f"  заголовок: {info['description']}")
            print(report(info, indent="  "))
            print()


if __name__ == "__main__":
    main()
