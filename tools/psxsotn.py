#!/usr/bin/env python3
"""Разбор сейва Castlevania: Symphony of the Night.

Смещения - от начала блока сейва, источник: game-tools-collection,
шаблон castlevania-symphony-of-the-night.
"""

import struct

import psxid
import psxsotndata as data

SERIALS = ("SLUS-00067", "SLES-00524", "SLPM-86023", "SCPS-45196")

# Шаблон адресуется от начала данных игры. Где они начинаются, зависит от
# числа кадров иконки, и у SotN в коллекции есть сейвы обоих видов: 15 с тремя
# кадрами (данные с 0x200) и 7 с одним (с 0x100). Жёсткая поправка 0x100
# читала однокадровые мимо - процент карты выходил нулевым при подписи "3%".
# Считаем базу по самому блоку: psxid.template_base.

PROGRESSION = 0x124
LOCATION = 0x128
MAP_RATE = 0x12A          # uint16, делится на 9.42 - так игра показывает проценты
CHARACTER = 0x130

HP_CUR, HP_MAX = 0x374, 0x378
HEARTS_CUR, HEARTS_MAX = 0x37C, 0x380
MP_CUR, MP_MAX = 0x384, 0x388

LEVEL = 0x3BC
EXPERIENCE = 0x3C0
GOLD = 0x3C4
KILLS = 0x3C8

PLAY_H, PLAY_M, PLAY_S = 0x404, 0x408, 0x40C

# Экипировка: семь слотов подряд по четыре байта.
GEAR = ((0x3D4, "правая рука"), (0x3D8, "левая рука"), (0x3DC, "голова"),
        (0x3E0, "тело"), (0x3E4, "плащ"), (0x3E8, "аксессуар 1"),
        (0x3EC, "аксессуар 2"))
HAND_SLOTS = (0x3D4, 0x3D8)     # в руках свой список предметов, не общий

SPELLS_BASE = 0x156
SPELL_SLOTS = 8
INVENTORY_BASE = 0x15E

FAMILIAR_BASE = 0x418
FAMILIAR_SIZE = 0x0C
FAMILIAR_COUNT = 7

BESTIARY_SEEN = 0x758
BESTIARY_DROPS = 0x778

RELIC_ON = 3

MAP_DIVISOR = 9.42
CHARACTERS = {0: "Alucard", 1: "Richter", 2: "Maria"}


def is_sotn(frame):
    return psxid.serial_of(frame) in SERIALS


def _u32(block, offset):
    return struct.unpack_from("<I", block, offset)[0]


def _u16(block, offset):
    return struct.unpack_from("<H", block, offset)[0]


def _base(block):
    return psxid.template_base(block)


def _bit(block, base, index):
    return (block[_base(block) + base + index // 8] >> (index % 8)) & 1


def gear(block):
    out = []
    for offset, label in GEAR:
        value = _u32(block, _base(block) + offset)
        table = data.HANDS if offset in HAND_SLOTS else data.ITEMS
        if value in table:
            out.append((label, table[value]))
    return out


def relics(block):
    return [name for name, offset in data.RELICS
            if block[_base(block) + offset] == RELIC_ON]


def spells(block):
    out = []
    for slot in range(SPELL_SLOTS):
        value = block[_base(block) + SPELLS_BASE + slot]
        if value and value in data.SPELLS:
            out.append(data.SPELLS[value])
    return out


def inventory(block):
    return [(name, block[_base(block) + INVENTORY_BASE + index])
            for index, name in sorted(data.ITEMS.items())
            if block[_base(block) + INVENTORY_BASE + index]]


def familiars(block):
    out = []
    for index in range(FAMILIAR_COUNT):
        base = _base(block) + FAMILIAR_BASE + index * FAMILIAR_SIZE
        level = struct.unpack_from("<I", block, base)[0]
        if level:
            out.append((data.FAMILIARS.get(index, f"#{index}"), level,
                        struct.unpack_from("<I", block, base + 4)[0]))
    return out


def bestiary(block):
    seen = [name for index, name in sorted(data.ENEMIES.items())
            if _bit(block, BESTIARY_SEEN, index)]
    drops = [name for index, name in sorted(data.ENEMIES.items())
             if _bit(block, BESTIARY_DROPS, index)]
    return seen, drops


def overview(block, frame=None):
    if frame is not None and not is_sotn(frame):
        return None
    base = _base(block)
    if len(block) < base + 0x420:
        return None
    character = _u32(block, base + CHARACTER)
    return {
        "character": CHARACTERS.get(character, f"#{character}"),
        "level": _u32(block, base + LEVEL),
        "exp": _u32(block, base + EXPERIENCE),
        "gold": _u32(block, base + GOLD),
        "kills": _u32(block, base + KILLS),
        "hp": (_u32(block, base + HP_CUR), _u32(block, base + HP_MAX)),
        "mp": (_u32(block, base + MP_CUR), _u32(block, base + MP_MAX)),
        "hearts": (_u32(block, base + HEARTS_CUR), _u32(block, base + HEARTS_MAX)),
        "map": round(_u16(block, base + MAP_RATE) / MAP_DIVISOR, 2),
        "location": block[base + LOCATION],
        "progression": block[base + PROGRESSION],
        "playtime": (_u32(block, base + PLAY_H), _u32(block, base + PLAY_M), _u32(block, base + PLAY_S)),
        "gear": gear(block),
        "relics": relics(block),
        "spells": spells(block),
        "inventory": inventory(block),
        "familiars": familiars(block),
        "bestiary": bestiary(block)[0],
        "drops": bestiary(block)[1],
        "enemy_total": len(data.ENEMIES),
    }


def report(info, indent=""):
    hours, minutes, seconds = info["playtime"]
    return "\n".join([
        f"{indent}{info['character']}, уровень {info['level']}",
        f"{indent}наиграно {hours}:{minutes:02d}:{seconds:02d}",
        f"{indent}HP {info['hp'][0]}/{info['hp'][1]} · "
        f"MP {info['mp'][0]}/{info['mp'][1]} · "
        f"сердца {info['hearts'][0]}/{info['hearts'][1]}",
        f"{indent}опыт {info['exp']} · золото {info['gold']} · "
        f"убийств {info['kills']}",
        f"{indent}карта пройдена на {info['map']} %",
        f"{indent}экипировка: " + (", ".join(f"{n}" for _, n in info["gear"]) or "—"),
        f"{indent}реликвий: {len(info['relics'])} из {len(data.RELICS)}",
        f"{indent}заклинаний: {len(info['spells'])} — "
        + (", ".join(info["spells"]) or "нет"),
        f"{indent}предметов: {len(info['inventory'])}",
        f"{indent}бестиарий: {len(info['bestiary'])} из {info['enemy_total']}"
        f", с дропом {len(info['drops'])}",
    ])
