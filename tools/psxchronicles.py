"""Разбор сейва Castlevania Chronicles.

Публичного разбора этой игры нет - раскладка найдена якорем по экрану
выбора игрока: он показывает имя и два числа, и они нашлись в байтах
один в один на трёх сейвах коллекции.

Уровень игра не хранит, а выводит из номера стейджа: их по три на
уровень, как в оригинальной Castlevania, ремейком которой Chronicles
и является. Проверено на стейджах 4, 13 и 16 - второй, пятый и шестой
уровни соответственно.
"""

import struct

import psxid

SERIALS = {"SLUS-01384", "SLES-03449", "SLPM-86808", "SLPM-86809"}

# Смещения от начала данных игры.
YEAR = 0x102        # u16
MONTH, DAY = 0x104, 0x105
HOUR, MINUTE, SECOND = 0x106, 0x107, 0x108
NAME, NAME_SIZE = 0x11A, 8
# Символ-заполнитель в имени: игра рисует его точкой.
FILLER = 0x5B
# Два числа, которые игра показывает под заголовком «stage».
STAGE, COUNTER = 0x124, 0x125
STAGES_PER_LEVEL = 3
# **Номера стейджей не сбрасываются на втором круге.** Стейдж 28 - это
# второй уровень второго прохождения, а не десятый уровень: в круге
# восемь уровней и двадцать четыре стейджа. Без этого выходили «уровни»
# за пределами игры. Проверено на пометках пользователя от 5-го до 8-го
# уровня и на его же словах про 28-й.
LEVELS_PER_LOOP = 8
STAGES_PER_LOOP = STAGES_PER_LEVEL * LEVELS_PER_LOOP

# **Записей две, через 0x30.** Читалась только первая, и три разных сейва
# показывали одинаковые «стейдж 28, уровень 10»: у второй записи там
# стейджи 16 и 22. Найдено сравнением трёх блоков побайтово - у второй
# записи то же поле имени (`SIMON` плюс заполнители) ровно через 0x30.
#
# **Первая запись - Original, вторая - Arrange.** Проверено на живой
# консоли: сейв с записями «стейдж 28» и «стейдж 16» игра показала в
# Original как 28, в Arrange как 16, число в число. Сейв с одной первой
# записью в Arrange не виден вовсе.
#
# Признака режима внутри записи нет: два сейва разных режимов
# различаются пятью байтами - время да стейдж со счётчиком. Режим задаёт
# номер записи, и узнать это можно было только опытом.
SLOT_STRIDE = 0x30
MODES = ("Original", "Arrange")
SLOTS = len(MODES)

# Признаки в первой записи, найденные сравнением сейвов до и после
# прохождения Arrange - изменились всего шесть байт.
ARRANGE_REACHED = 0x111   # докуда дошли в Arrange
ARRANGE_CLEARED = 0x114   # 1, когда Arrange пройден

# --- Time Attack ---
# Восемь таблиц рекордов, по числу уровней в круге, в каждой десять мест.
# Найдено якорем: пользователь проехал первый уровень с временем 3:26.2 и
# счётом 23500, и его строка встала первой, сдвинув остальные вниз.
# Заводские места подписаны `DRA` и идут ровным шагом: 7:00/3000,
# 7:40/2000, 8:20/1700 и дальше.
TA_FIRST = 0x17C          # первая таблица
TA_ENTRY = 0x10           # длина записи
TA_ROWS = 10              # мест в таблице
TA_TABLES = LEVELS_PER_LOOP
TA_NAME, TA_NAME_SIZE = 0x00, 8
TA_TIME = 0x0A            # десятые доли секунды, u16
TA_SCORE = 0x0C           # u16
# Имя заводских мест. Игрок с таким же именем неотличим - но он бы и на
# экране их не отличил.
TA_FACTORY = b"DRA\x00\x00\x00\x00\x00"


def is_chronicles(frame):
    return psxid.serial_of(frame) in SERIALS


def _slot(block, base, index):
    """Одна из двух записей игры."""
    at = base + index * SLOT_STRIDE
    if len(block) < at + 0x140:
        return None

    raw = bytes(block[at + NAME:at + NAME + NAME_SIZE])
    letters = []
    for byte in raw:
        if byte in (FILLER, 0):
            break
        letters.append(byte)
    name = bytes(letters).decode("ascii", "replace").strip()

    stage = block[at + STAGE]
    return {
        "mode": MODES[index],
        "slot": index + 1,
        "name": name,
        "stage": stage,
        # Что значит второе число - неизвестно, показываем как есть.
        "counter": block[at + COUNTER],
        "level": ((stage - 1) % STAGES_PER_LOOP) // STAGES_PER_LEVEL + 1
                 if stage else 0,
        "loop": (stage - 1) // STAGES_PER_LOOP + 1 if stage else 0,
        "saved": "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            struct.unpack_from("<H", block, at + YEAR)[0],
            block[at + MONTH], block[at + DAY],
            block[at + HOUR], block[at + MINUTE], block[at + SECOND]),
        # У вложенных записей эти поля всегда пусты, но быть должны:
        # у нового движка запись - одна структура, и он их всегда пишет.
        # Без них сверка движков видит расхождение на ровном месте.
        "slots": [],
        "timeAttack": [],
    }


def time_attack(block):
    """Рекорды Time Attack, поставленные игроком.

    Заводские места пропускаем: их десять на каждый из восьми уровней,
    и показывать восемьдесят строк заготовки незачем.
    """
    base = psxid.data_offset(block)
    found = []
    for table in range(TA_TABLES):
        for place in range(TA_ROWS):
            at = base + TA_FIRST + (table * TA_ROWS + place) * TA_ENTRY
            if at + TA_ENTRY > len(block):
                return found
            raw = bytes(block[at + TA_NAME:at + TA_NAME + TA_NAME_SIZE])
            if raw == TA_FACTORY:
                continue
            name = bytes(b for b in raw if b not in (FILLER, 0)).decode(
                "ascii", "replace").strip()
            tenths = struct.unpack_from("<H", block, at + TA_TIME)[0]
            if not name or not tenths:
                continue
            found.append({
                "level": table + 1,
                "place": place + 1,
                "name": name,
                "tenths": tenths,
                "time": "{}:{:04.1f}".format(tenths // 600, tenths % 600 / 10),
                "score": struct.unpack_from("<H", block, at + TA_SCORE)[0],
            })
    return found


def slots(block):
    """Заполненные записи. Пустая узнаётся по имени: игра оставляет там
    одни заполнители, пока в этом режиме не сохранялись."""
    base = psxid.data_offset(block)
    found = []
    for index in range(SLOTS):
        got = _slot(block, base, index)
        if got and got["name"]:
            found.append(got)
    return found


def overview(block):
    base = psxid.data_offset(block)
    first = _slot(block, base, 0)
    if first is None:
        return None
    first = dict(first)
    first["slots"] = slots(block)
    first["timeAttack"] = time_attack(block)
    return first
