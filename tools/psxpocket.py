#!/usr/bin/env python3
"""PocketStation: определение приложений и разбор состояния Chocobo World.

Одна и та же 64-байтовая запись живёт в двух местах:
  * в сейве Chocobo World на стороне PocketStation - в двух банках;
  * внутри сейва FF8 - блок CHOCOBO по смещению 5344 блока данных.
Раскладка полей идентична, поэтому обе читаются одним разбором.
"""

import struct

RECORD_SIZE = 64

# --- Сторона FF8 ---
# Проверка "это вообще FF8" и положение блока - по hyne, SaveData.cpp/SaveData.h.
FF8_MAGIC_OFFSET = 386
FF8_MAGIC = (0x08FF, 0x0FF8)
FF8_CHOCOBO_OFFSET = 5344

# --- Сторона PocketStation ---
# ChocoEdit держит два банка и выбирает свежий по счётчику сохранений.
# У него смещения от начала .mcs (0x280/0x380), здесь - от начала блока данных.
POCKET_BANKS = (0x200, 0x300)
POCKET_SAVE_SIZE = 57472  # 128 байт заголовка .mcs + 7 блоков

# --- Признаки приложения PocketStation ---
# По MemcardRex, loadSlotDataTypes: 'P' в имени сейва плюс магия в блоке.
#
# **`CRD0` - тоже приложение.** MemcardRex его исключает намеренно, и в
# комментарии там сказано почему: `CRD0` не заставляет браузер PS2
# показывать запись как «software». Но это ответ на другой вопрос - как
# запись выглядит на PS2, - а нам надо знать, приложение это или сейв.
# С `CRD0` идут семь настоящих приложений коллекции: Brightis, PokeHito,
# R4, Rockman 3, Doraemon 3, Chivas и Parumui. Скопировав критерий, я
# скопировал и чужую цель.
APP_NAME_INDEX = 6
APP_MAGIC_OFFSET = 0x52
APP_MAGICS = (b"MCX0", b"MCX1", b"CRD0")
# Показывается ли запись приложением в браузере PS2 - отдельный вопрос.
PS2_BROWSER_MAGICS = (b"MCX0", b"MCX1")

# Имена битов по ChocoEdit, кроме нулевого: тот у ChocoEdit зовётся Eventflag0
# с пометкой «назначение неясно», а у hyne это Enabled - главный выключатель
# Chocobo World, и пишет его hyne именно так (CWEditor.cpp:204).
# С третьего бита названия у двух программ расходятся, а байт один и тот же.
MOG_FLAGS = [
    (0x01, "Chocobo World включён"),
    (0x02, "Боко в отлучке"),
    (0x04, "MiniMog найден"),
    (0x08, "MiniMog получен"),
    (0x10, "MiniMog в ожидании"),
    (0x20, "Король демонов побеждён"),
    (0x40, "событие просмотрено"),
    (0x80, "Event wait выключен"),
]

SUMMON_LEVELS = ["нет", "ChocoFire", "ChocoFlare", "ChocoMeteor", "ChocoBocle"]


def bcd(value):
    """Числовые поля записи хранятся в BCD: 42 лежит в байте как 0x42."""
    return (value >> 4) * 10 + (value & 0xF)


def is_bcd(value):
    return (value >> 4) <= 9 and (value & 0xF) <= 9


def read_record(buf, base):
    """Разбирает 64-байтовую запись Chocobo World."""
    if len(buf) < base + RECORD_SIZE:
        return None
    rec = buf[base:base + RECORD_SIZE]

    flags = rec[0]
    level = bcd(rec[1]) or 100  # 0 в поле уровня означает 100

    record = {
        "flags": flags,
        "flag_names": [name for bit, name in MOG_FLAGS if flags & bit],
        "level": level,
        "hp": bcd(rec[2]),
        "hp_max": bcd(rec[3]),
        # Четыре десятичные цифры в двух байтах, младшая пара - первая.
        "weapon": bcd(rec[5]) * 100 + bcd(rec[4]),
        "rank": bcd(rec[6]),
        "move": rec[7],
        "save_count": struct.unpack_from("<I", rec, 8)[0],
        "id": (rec[13] & 0xF) * 100 + bcd(rec[12]),
        "items": [bcd(rec[0x14 + i]) for i in range(4)],
        "ff8_id": struct.unpack_from("<I", rec, 0x28)[0],
        "summon": rec[0x2D],
        "home_walking": rec[0x2F],
        "raw": bytes(rec[:8]),
    }
    record["summon_name"] = (SUMMON_LEVELS[record["summon"]]
                             if record["summon"] < len(SUMMON_LEVELS) else "?")
    record["bcd_valid"] = all(is_bcd(rec[i])
                              for i in (1, 2, 3, 6, 0x14, 0x15, 0x16, 0x17))
    # Hyne читает те же байты без BCD. До 9 показания совпадают, дальше - нет.
    record["bcd_ambiguous"] = any(rec[i] > 0x09 for i in (1, 2, 3))
    record["raw_level"] = rec[1]
    return record


def plausible(record):
    """Отсеивает мусор. Записи Chocobo World ищутся в блоках любых игр,
    поэтому критерии жёсткие: всё поле должно быть валидным BCD и лежать
    в игровых пределах, а HP - не превышать максимум."""
    if record is None:
        return False
    if not record["bcd_valid"]:
        return False
    if not 1 <= record["level"] <= 100:
        return False
    if not 1 <= record["hp"] <= 99:
        return False
    if not 6 <= record["hp_max"] <= 99:
        return False
    if record["hp"] > record["hp_max"]:
        return False
    if record["rank"] > 6 or record["move"] > 5:
        return False
    if record["summon"] > 4:
        return False
    if any(item > 99 for item in record["items"]):
        return False
    # Счётчик сохранений у прожитой игры всегда ненулевой и не астрономический.
    return 0 < record["save_count"] < 1_000_000


def from_ff8_save(block):
    """Блок CHOCOBO внутри сейва Final Fantasy VIII."""
    if len(block) < FF8_MAGIC_OFFSET + 2:
        return None
    magic = struct.unpack_from("<H", block, FF8_MAGIC_OFFSET)[0]
    if magic not in FF8_MAGIC:
        return None
    record = read_record(block, FF8_CHOCOBO_OFFSET)
    if not plausible(record):
        return None
    record["source"] = "блок CHOCOBO в сейве FF8"
    return record


def from_pocketstation_save(block, directory_frame):
    """Сейв Chocobo World: два банка, свежий определяется счётчиком.

    Ищется только в приложениях PocketStation - иначе два произвольных
    смещения в чужом блоке слишком легко дают правдоподобный мусор."""
    if directory_frame is None or not is_application(directory_frame, block):
        return None
    banks = [r for r in (read_record(block, base) for base in POCKET_BANKS)
             if plausible(r)]
    if not banks:
        return None
    record = max(banks, key=lambda r: r["save_count"])
    record["source"] = f"Chocobo World, живых банков: {len(banks)}"
    return record


def find_chocobo(block, directory_frame=None):
    return from_ff8_save(block) or from_pocketstation_save(block, directory_frame)


def is_application(directory_frame, block):
    """Приложение PocketStation, а не обычный сейв."""
    name = directory_frame[10:30]
    if len(name) <= APP_NAME_INDEX or name[APP_NAME_INDEX] != 0x50:
        return False
    return block[APP_MAGIC_OFFSET:APP_MAGIC_OFFSET + 4] in APP_MAGICS


def shows_on_ps2(block):
    """Показывает ли браузер PS2 эту запись приложением, а не сейвом."""
    return block[APP_MAGIC_OFFSET:APP_MAGIC_OFFSET + 4] in PS2_BROWSER_MAGICS


def summary(record):
    """Однострочное описание для CLI."""
    parts = [f"Боко ур.{record['level']}",
             f"HP {record['hp']}/{record['hp_max']}",
             f"ранг {record['rank']}"]
    if record["summon"]:
        parts.append(record["summon_name"])
    if any(record["items"]):
        parts.append("предметы " + "/".join(str(i) for i in record["items"]))
    return ", ".join(parts)


# --- Привязка Боко к конкретному сейву FF8 ------------------------------------
# ChocoEdit читает uint32 по 0x1588 из .mcs с сейвом FF8 и кладёт его в поле
# FF8ID записи Chocobo World (MainForm.cs, Ff8id_setClick). 0x1588 минус
# 128-байтовый заголовок .mcs даёт 5384, то есть CHOCOBO+0x28 - это одно и то же
# поле, associatedSaveID у hyne. Привязка сводится к переносу этих четырёх байт.

LINK_FIELD = 0x28
ENABLED_BIT = 0x01
AWAY_BIT = 0x02
HOME_WALKING = 0x2F


def read_link(record_bytes):
    return struct.unpack_from("<I", record_bytes, LINK_FIELD)[0]


def with_link(record_bytes, value):
    out = bytearray(record_bytes)
    struct.pack_into("<I", out, LINK_FIELD, value)
    return bytes(out)


def with_flags(record_bytes, enabled=None, away=None, walking=None):
    """Правит флаги записи.

    Бит 0 включает Chocobo World, бит 1 означает, что Боко в отлучке. ChocoEdit
    оба писать отказывается - строки закомментированы 'for safety'
    (MainForm.cs:312-313). Hyne пишет оба, но не трогает home_walking:
    поле объявлено в SaveData.h и больше нигде не встречается."""
    out = bytearray(record_bytes)
    for bit, value in ((ENABLED_BIT, enabled), (AWAY_BIT, away)):
        if value is None:
            continue
        out[0] = (out[0] | bit) if value else (out[0] & ~bit & 0xFF)
    if walking is not None:
        out[HOME_WALKING] = 1 if walking else 0
    return bytes(out)
