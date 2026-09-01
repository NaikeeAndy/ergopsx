"""Разбор сейва Vagrant Story.

**Сейв зашифрован** - поточный шифр на линейном конгруэнтном генераторе
(`_decode` из `ser-pounce/rood-reverse`, MENU7.PRG): ключ лежит открытым
текстом по 0x180, дальше на каждый байт ключ умножается на 0x19660D, и
старший байт результата вычитается из байта данных. Именно из-за шифра
игру нигде и не разбирали.

Раскладка - `savedata_t` оттуда же. Смещения не выводились: они стоят
прямо в именах полей декомпиляции (`unk6C8`, `unk16C8`, `unk1898`).

Названия предметов и действий лежат в `tools/data/vagrant-map.json`:
предметы взяты из `MENU/ITEMNAME.BIN` на диске, действия - из таблицы
`vs_main_actions[]` в декомпиляции.
"""

import json
import os
import struct

import psxid

SERIALS = {"SLUS-01040", "SLES-02754", "SLES-02755", "SLES-02756",
           "SLPS-02377", "SLPS-91457", "SLPM-87393", "SCPS-45486"}

KEY_AT = 0x180            # ключ шифра, четыре байта открытым текстом
CIPHER_FROM = 0x184       # отсюда и до конца - шифрованное
MULTIPLIER = 0x19660D
# Магия расшифрованного заголовка: по ней и проверяем, что расшифровали
# верно, а не получили новый мусор.
MAGIC, MAGIC_AT = 0x20000107, 0x18C

STATS = 0x190
GENERATION = 0x188
ACTIONS_LEARNED, ACTIONS_SIZE = 0x640, 32
MAP_STATUS, MAP_STATUS_SIZE = 0x660, 0x48
ROOM_FLAGS, ROOM_WORDS = 0x660, 16
AREA_FLAGS = 0x6A0
ARTS, ARTS_SIZE = 0x1DBC, 12
ARTS_ABILITIES = 0x1DDC
SCORE = 0x1784
SCORE_KILLS = 0x04
SCORE_MAX_CHAIN = 0x88
SCORE_ROOMS = 0x94
SCORE_CHESTS = 0x98
SCORE_HEALS = 0x112

# Разделы инвентаря: ключ, смещение, размер записи, мест, где номер
# предмета и его ширина. У оружия номера нет - оно собрано из клинка и
# рукояти, а имя даёт игрок.
CARRIED = (
    ("weapons", "Оружие", 0x07C8, 32, 8, None, False),
    ("shields", "Щиты", 0x08C8, 48, 8, 4, False),
    ("blades", "Клинки", 0x0A48, 44, 16, 0, False),
    ("grips", "Рукояти", 0x0D08, 16, 16, 0, True),
    ("armor", "Броня", 0x0E08, 40, 16, 0, False),
    ("gems", "Самоцветы", 0x1088, 28, 48, 0, True),
    ("misc", "Прочее", 0x15C8, 4, 64, 0, True),
)
STORED = (
    ("weapons", "Оружие", 0x1DE0, 32, 32, None, False),
    ("shields", "Щиты", 0x21E0, 48, 32, 4, False),
    ("blades", "Клинки", 0x27E0, 44, 64, 0, False),
    ("grips", "Рукояти", 0x32E0, 16, 64, 0, True),
    ("armor", "Броня", 0x36E0, 40, 64, 0, False),
    ("gems", "Самоцветы", 0x40E0, 28, 192, 0, True),
    ("misc", "Прочее", 0x55E0, 4, 256, 0, True),
)
WEAPON_NAME, WEAPON_NAME_SIZE = 8, 24

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "vagrant-map.json")
_table = None


def table():
    global _table
    if _table is None:
        try:
            with open(DATA_PATH, encoding="utf-8") as fh:
                _table = json.load(fh)
        except (OSError, ValueError):
            _table = {}
    return _table


def is_vagrant(frame):
    return psxid.serial_of(frame) in SERIALS


def decode(block):
    """Расшифровка на месте. Ключ остаётся как есть - он не шифрован."""
    if len(block) <= CIPHER_FROM:
        return bytes(block)
    out = bytearray(block)
    key = struct.unpack_from("<I", out, KEY_AT)[0]
    for index in range(CIPHER_FROM, len(out)):
        key = (key * MULTIPLIER) & 0xFFFFFFFF
        out[index] = (out[index] - ((key >> 24) & 0xFF)) & 0xFF
    return bytes(out)


# Кодировка текста игры: буквы, цифры и знаки. Полная таблица - в
# `reference/.../vsString.py`, здесь нужен только печатный диапазон.
def _text(raw):
    out = []
    index = 0
    while index < len(raw):
        code = raw[index]
        if code == 0xE7:                      # конец строки
            break
        if code == 0xEB:                      # выравнивание
            index += 1
            continue
        if code == 0xFA:                      # кернинг - пробел между слов
            out.append(" ")
            index += 2
            continue
        if 0xEC <= code <= 0xFF:              # прочие управляющие с аргументом
            index += 2
            continue
        if code < 10:
            out.append(chr(ord("0") + code))
        elif code < 0x24:
            out.append(chr(ord("A") + code - 0x0A))
        elif code < 0x3E:
            out.append(chr(ord("a") + code - 0x24))
        elif code == 0x8F:
            out.append(" ")
        index += 1
    return " ".join("".join(out).split())


def _u16(block, at):
    return struct.unpack_from("<H", block, at)[0]


def _u32(block, at):
    return struct.unpack_from("<I", block, at)[0]


def _used(plain, at, size, slots):
    return [index for index in range(slots)
            if at + (index + 1) * size <= len(plain)
            and any(plain[at + index * size:at + (index + 1) * size])]


def overview(block):
    if len(block) < 0x59E0:
        return None
    plain = decode(block)
    # Если магия не встала на место - расшифровали не то, и читать
    # дальше значило бы выдумывать числа.
    if _u32(plain, MAGIC_AT) != MAGIC:
        return None

    data = table()
    items = data.get("items") or []
    actions = data.get("actions") or []
    mask = data.get("mask") or []
    scenes = data.get("scenes") or []
    areas = data.get("areas") or []

    hours, minutes, seconds = plain[STATS + 3], plain[STATS + 2], plain[STATS + 1]

    def section_items(spec):
        # Ключ - устойчивый признак раздела, а не его название: название
        # переводится, и привязываться к нему нельзя.
        out = {}
        for kind, _name, at, size, slots, id_at, wide in spec:
            if id_at is None:
                continue
            counts, order = {}, []
            for index in _used(plain, at, size, slots):
                start = at + index * size + id_at
                number = _u16(plain, start) if wide else plain[start]
                if not number or number >= len(items):
                    continue
                shown = items[number] or f"#{number}"
                if shown not in counts:
                    order.append(shown)
                counts[shown] = counts.get(shown, 0) + 1
            if order:
                out[kind] = [(shown, counts[shown]) for shown in order]
        return out

    def weapon_names(spec):
        _, _, at, size, slots, _, _ = spec[0]
        out = []
        for index in _used(plain, at, size, slots):
            start = at + index * size + WEAPON_NAME
            name = _text(plain[start:start + WEAPON_NAME_SIZE])
            # Место занято, но не подписано: в кодировке игры ноль -
            # это цифра «0», и пустое имя выглядит строкой нулей.
            if not name.strip("0 "):
                name = "без имени"
            out.append(name)
        return out

    # Бит выученного действия считается со старшего - как в INITBTL.PRG.
    learned = {}
    for index in range(min(256, len(actions))):
        byte = ACTIONS_LEARNED + (index >> 3)
        if byte >= len(plain):
            break
        if not plain[byte] & (0x80 >> (index & 7)):
            continue
        action = actions[index]
        if action.get("n") and action.get("k"):
            learned.setdefault(action["k"], []).append(action["n"])

    rooms = [_u32(plain, ROOM_FLAGS + word * 4) for word in range(ROOM_WORDS)]
    # Поправка, которую игра делает перед подсчётом процента.
    if rooms[1] & 0x800000:
        rooms[1] |= 0x400000
    unopened = {}
    for room in range(ROOM_WORDS * 32):
        word, bit = room // 32, room % 32
        if word >= len(mask) or not mask[word] >> bit & 1:
            continue
        if rooms[word] >> bit & 1:
            continue
        scene = scenes[room] if room < len(scenes) else -1
        name = areas[scene] if 0 <= scene < len(areas) and areas[scene] \
            else "неизвестно"
        unopened[name] = unopened.get(name, 0) + 1

    return {
        "playtime": [hours, minutes, seconds],
        "hp": [_u16(plain, STATS + 0x08), _u16(plain, STATS + 0x0A)],
        "mp": [_u16(plain, STATS + 0x10), _u16(plain, STATS + 0x12)],
        "location": plain[STATS + 0x0C],
        "clear_count": plain[STATS + 0x0D],
        "map_completion": plain[STATS + 0x0E],
        "saves_total": _u16(plain, STATS + 0x04),
        "saves_game": _u16(plain, STATS + 0x06),
        "generation": _u32(plain, GENERATION),
        "rooms": _u32(plain, SCORE + SCORE_ROOMS),
        "rooms_total": data.get("rooms_total", 361),
        "chests": _u32(plain, SCORE + SCORE_CHESTS),
        "max_chain": _u16(plain, SCORE + SCORE_MAX_CHAIN),
        "heals": _u16(plain, SCORE + SCORE_HEALS),
        "kills": [_u16(plain, SCORE + SCORE_KILLS + i * 2) for i in range(6)],
        # Двенадцать счётчиков, а не биты: у каждой категории оружия
        # от нуля до четырёх приёмов.
        # Открытые способности и число разделов карты, где герой побывал.
        # Обоих полей тут не было, а у движка на Swift они есть - сверка
        # движков этого не показала: она сравнивает только общий набор.
        "abilities": _u16(plain, ARTS_ABILITIES),
        "maps": sum(1 for byte in plain[MAP_STATUS:MAP_STATUS + MAP_STATUS_SIZE]
                    if byte),
        "arts_learned": sum(plain[ARTS:ARTS + ARTS_SIZE]),
        "arts_by_category": list(plain[ARTS:ARTS + ARTS_SIZE]),
        "actions": sum(bin(byte).count("1")
                       for byte in plain[ACTIONS_LEARNED:
                                         ACTIONS_LEARNED + ACTIONS_SIZE]),
        "learned": learned,
        "weapons": weapon_names(CARRIED),
        "stored_weapons": weapon_names(STORED),
        "carried_items": section_items(CARRIED),
        "stored_items": section_items(STORED),
        "unopened": unopened,
    }
