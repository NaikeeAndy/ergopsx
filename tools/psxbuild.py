#!/usr/bin/env python3
"""Сборка образа карты памяти PS1 из отдельных сейвов.

    psxbuild.py list  <файл>...                     что можно взять
    psxbuild.py make  -o card.mcr <файл>...         собрать карту
    psxbuild.py check <card.mcr>                    проверить готовый образ

Берёт сейвы из любых контейнеров (PSV с PS3, MCS, GME, VMP, образы карт) и
складывает их в один образ на 128 КБ. Нужно, чтобы отнести сейвы с PS3
в эмулятор: DuckStation, ePSXe и Beetle читают именно образ карты.

Ничего не перезаписывает: существующий файл не трогает без --force.

Раскладка выяснена по настоящим картам, а не по описанию:
- продолжение многоблочного сейва - состояние 0x53, нулевой размер, пустое имя;
- поле "следующий блок" считает от нуля, то есть номер блока минус один
  (у Suikoden блок 1 указывает на 0x0001, а это блок 2);
- резервная область фреймов 16..62 одинакова у всех 176 карт коллекции.
"""

import argparse
import os
import struct
import sys

import psxid
import psxsign

CARD_SIZE = psxid.BLOCK * 16          # 131072
FIRST = 0x51                          # начало сейва
MIDDLE = 0x52                         # продолжение
LAST = 0x53                           # последний блок цепочки
FREE = 0xA0                           # свободный слот
DELETED = 0xA1                        # удалённый сейв, данные ещё на месте
END = 0xFFFF                          # цепочка кончилась


def _xor(frame):
    value = 0
    for byte in frame[:psxid.FRAME - 1]:
        value ^= byte
    return value


def _seal(frame):
    """Дописывает контрольный байт XOR в конец фрейма."""
    frame = bytearray(frame)
    frame[psxid.FRAME - 1] = _xor(frame)
    return bytes(frame)


def _header_frame():
    return _seal(b"MC" + bytes(psxid.FRAME - 2))


def _free_frame():
    frame = bytearray(psxid.FRAME)
    frame[0] = FREE
    struct.pack_into("<H", frame, 8, END)
    return _seal(frame)


def _reserve():
    """Фреймы 16..63: список сбойных секторов и проверочный фрейм."""
    out = bytearray()
    for _ in range(20):                       # 16..35 - список сбойных
        frame = bytearray(psxid.FRAME)
        struct.pack_into("<I", frame, 0, 0xFFFFFFFF)
        struct.pack_into("<H", frame, 8, END)
        out += _seal(frame)
    out += bytes(psxid.FRAME * 27)            # 36..62 - пусто
    out += _header_frame()                    # 63 - проверочный
    return bytes(out)


def _name_of(raw):
    return bytes(raw).split(b"\x00")[0].decode("ascii", errors="replace").strip()


def sources(path):
    """Сейвы из файла: [{name, blocks, where, title}]. Многоблочные - целиком."""
    with open(path, "rb") as fh:
        blob = fh.read()

    if blob[:4] == psxsign.PSV["magic"]:
        size = struct.unpack_from("<I", blob, 0x40)[0]
        start = struct.unpack_from("<I", blob, 0x44)[0]
        return [{"name": bytes(blob[0x64:0x78]), "where": "PSV",
                 "blocks": _split(blob[start:start + size])}]
    if blob[:1] == b"Q":
        frame = blob[:psxid.FRAME]
        size = struct.unpack_from("<I", frame, 4)[0] or (len(blob) - psxid.FRAME)
        return [{"name": bytes(frame[10:30]), "where": "MCS",
                 "blocks": _split(blob[psxid.FRAME:psxid.FRAME + size])}]
    if blob[:2] in (b"SC", b"sc"):
        stem = os.path.splitext(os.path.basename(path))[0]
        found = psxid.EMBEDDED_NAME.search(stem)
        name = (found.group(0) if found else stem).encode("ascii", "replace")[:20]
        return [{"name": name, "where": "блок без заголовка",
                 "blocks": _split(blob)}]

    data, label = psxid.find_card_data(blob)
    if data is None:
        raise ValueError(f"{os.path.basename(path)}: формат не распознан")
    return _from_card(data, label)


def _split(payload):
    """Полезные данные -> список блоков по 8192, добивая нулями."""
    if not payload:
        raise ValueError("пустой сейв")
    count = max(1, (len(payload) + psxid.BLOCK - 1) // psxid.BLOCK)
    payload = payload.ljust(count * psxid.BLOCK, b"\x00")
    return [bytes(payload[i * psxid.BLOCK:(i + 1) * psxid.BLOCK])
            for i in range(count)]


def _from_card(data, label):
    """Сейвы из образа карты, с проходом по цепочке блоков.

    Блоки многоблочного сейва лежат не обязательно подряд, поэтому идём по
    ссылкам, а не по порядку.

    Удалённые сейвы (0xA1) тоже берём: BIOS при удалении меняет только байт
    состояния, данные и имя остаются на месте, поэтому на новой карте такой
    сейв оживает. Нумерация совпадает с psxchoco.scan - по ней приложение
    указывает, какой сейв выбран."""
    out = []
    for slot in range(psxid.SLOTS):
        frame = data[psxid.FRAME * (slot + 1):psxid.FRAME * (slot + 2)]
        if not frame:
            continue
        _, is_head = psxid.SLOT_STATES.get(frame[0], ("corrupt", False))
        if not is_head:
            continue
        size = struct.unpack_from("<I", frame, 4)[0]
        want = max(1, size // psxid.BLOCK) if size else 1
        chain, current, seen = [slot], slot, {slot}
        while len(chain) < want:
            link = data[psxid.FRAME * (current + 1):psxid.FRAME * (current + 2)]
            nxt = struct.unpack_from("<H", link, 8)[0]
            if nxt == END or nxt >= psxid.SLOTS or nxt in seen:
                break
            current = nxt
            seen.add(current)
            chain.append(current)
        blocks = [bytes(data[psxid.BLOCK * (i + 1):psxid.BLOCK * (i + 2)])
                  for i in chain]
        if len(blocks) < want:
            raise ValueError(f"{_name_of(frame[10:30])}: цепочка оборвана "
                             f"({len(blocks)} из {want} блоков)")
        out.append({"name": bytes(frame[10:30]), "blocks": blocks,
                    "deleted": frame[0] == DELETED,
                    "where": f"{label}, слот {slot + 1}"})
    return out


def build(entries):
    """Собирает образ на 128 КБ.

    Возвращает (образ, расклад по слотам, отброшенные дубли)."""
    # Консоль и игры находят сейв по имени, поэтому двух одинаковых имён на
    # карте быть не должно. Побайтовый дубль отбрасываем молча - он ничего не
    # теряет; а вот разные сейвы под одним именем выбирать за пользователя
    # нельзя.
    seen, unique, dropped = {}, [], []
    for entry in entries:
        key = _name_of(entry["name"])
        first = seen.get(key)
        if first is None:
            seen[key] = entry
            unique.append(entry)
            continue
        if first["blocks"] == entry["blocks"]:
            dropped.append((key, entry["where"]))
            continue
        raise ValueError(f"два разных сейва с одним именем '{key}': "
                         f"{first['where']} и {entry['where']}. Игра находит "
                         "сейв по имени и различить их не сможет - оставьте один")
    entries = unique

    need = sum(len(e["blocks"]) for e in entries)
    if need > psxid.SLOTS:
        raise ValueError(f"нужно {need} блоков, а на карте только {psxid.SLOTS}")

    frames = [_free_frame() for _ in range(psxid.SLOTS)]
    blocks = [bytes(psxid.BLOCK) for _ in range(psxid.SLOTS)]
    layout, cursor = [], 0
    for entry in entries:
        chain = list(range(cursor, cursor + len(entry["blocks"])))
        size = len(entry["blocks"]) * psxid.BLOCK
        for position, slot in enumerate(chain):
            frame = bytearray(psxid.FRAME)
            blocks[slot] = entry["blocks"][position]
            if position == 0:
                frame[0] = FIRST
                struct.pack_into("<I", frame, 4, size)
                # Ссылка считает от нуля: номер блока минус один.
                struct.pack_into("<H", frame, 8,
                                 chain[1] if len(chain) > 1 else END)
                name = bytes(entry["name"])[:20].ljust(20, b"\x00")
                frame[10:30] = name
            else:
                last = position == len(chain) - 1
                frame[0] = LAST if last else MIDDLE
                struct.pack_into("<H", frame, 8,
                                 END if last else chain[position + 1])
            frames[slot] = _seal(frame)
        layout.append({"name": _name_of(entry["name"]), "where": entry["where"],
                       "block": chain[0] + 1, "blocks": len(chain),
                       "restored": bool(entry.get("deleted"))})
        cursor += len(chain)

    card = bytearray(_header_frame())
    for frame in frames:
        card += frame
    card += _reserve()
    for block in blocks:
        card += block
    assert len(card) == CARD_SIZE, len(card)
    return bytes(card), layout, dropped


def check(card):
    """Разбирает готовый образ: [(слот, состояние, блоков, имя)] или ошибка."""
    if len(card) != CARD_SIZE:
        raise ValueError(f"размер {len(card)}, а должен быть {CARD_SIZE}")
    if card[:2] != b"MC":
        raise ValueError("нет магии 'MC' в начале")
    bad = [n for n in range(64)
           if _xor(card[psxid.FRAME * n:psxid.FRAME * (n + 1)])
           != card[psxid.FRAME * n + psxid.FRAME - 1]]
    if bad:
        raise ValueError(f"неверная контрольная сумма у фреймов {bad}")
    return _from_card(card, "образ")


def as_gme(card):
    """Обёртка DexDrive: заголовок на 3904 байта."""
    head = bytearray(b"123-456-STD".ljust(11, b"\x00") + bytes(3904 - 11))
    head[18] = 0x1
    head[20] = 0x1
    head[21] = 0x4D
    return bytes(head) + card


def as_vmp(card):
    """Обёртка PSP с пересчитанной подписью."""
    head = bytearray(psxid.BLOCK // 64)
    head[0:4] = psxsign.VMP["magic"]
    struct.pack_into("<I", head, 4, 0x80)
    struct.pack_into("<I", head, 8, CARD_SIZE)
    blob = bytes(head) + card
    return psxsign.resign(blob)


WRAPPERS = {".gme": as_gme, ".vmp": as_vmp}  # .mcr и .mcd - без обёртки


def command_list(paths):
    titles = psxid.load_titles(psxid.default_titles_path())
    total = 0
    for path in paths:
        print(os.path.basename(path))
        try:
            found = sources(path)
        except Exception as error:
            print(f"    ! {error}")
            continue
        for entry in found:
            name = _name_of(entry["name"])
            title = titles.get(psxid.normalize_serial(name[2:12]), "")
            total += len(entry["blocks"])
            print(f"    {name:<22} {len(entry['blocks'])} бл.  {title[:38]}")
    print(f"\nвсего блоков: {total} из {psxid.SLOTS}")


def command_make(paths, output, force):
    if os.path.exists(output) and not force:
        sys.exit(f"'{output}' уже существует. Укажите другое имя или --force")
    entries = []
    for path in paths:
        spec, _, want = path.rpartition("#")
        found = sources(spec or path)
        if want.isdigit():
            index = int(want)
            if index >= len(found):
                sys.exit(f"в '{spec}' нет сейва №{index}")
            found = [found[index]]
        entries += found

    card, layout, dropped = build(entries)
    for name, where in dropped:
        print(f"пропущен дубль: {name} ({where}) — байт в байт совпадает с уже взятым")
    suffix = os.path.splitext(output)[1].lower()
    blob = WRAPPERS.get(suffix, lambda c: c)(card)

    with open(output, "wb") as fh:
        fh.write(blob)

    titles = psxid.load_titles(psxid.default_titles_path())
    print(f"{'блок':>5}  {'имя':<22} {'бл.':>3}  игра")
    for row in layout:
        title = titles.get(psxid.normalize_serial(row["name"][2:12]), "")
        mark = "  (был удалён, восстановлен)" if row["restored"] else ""
        print(f"{row['block']:>5}  {row['name']:<22} {row['blocks']:>3}  "
              f"{title[:34]}{mark}")
    used = sum(r["blocks"] for r in layout)
    print(f"\nзаписано: {output} ({len(blob)} байт), "
          f"занято {used} из {psxid.SLOTS} блоков")
    # Читаем то, что записали: если тут разошлось, наружу это не выпустим.
    back = check(card)
    assert len(back) == len(layout), "образ читается иначе, чем собирался"
    for entry, row in zip(back, entries):
        assert entry["blocks"] == row["blocks"], f"блоки {_name_of(entry['name'])}"
    print("проверено: образ перечитан, все сейвы на месте байт в байт")


def command_check(paths):
    titles = psxid.load_titles(psxid.default_titles_path())
    for path in paths:
        print(os.path.basename(path))
        with open(path, "rb") as fh:
            blob = fh.read()
        data, _ = psxid.find_card_data(blob)
        if data is None:
            print("    ! это не образ карты")
            continue
        try:
            found = check(bytes(data[:CARD_SIZE]))
        except ValueError as error:
            print(f"    ! {error}")
            continue
        used = sum(len(e["blocks"]) for e in found)
        for entry in found:
            name = _name_of(entry["name"])
            print(f"    {name:<22} {len(entry['blocks'])} бл.  "
                  f"{titles.get(psxid.normalize_serial(name[2:12]), '')[:34]}")
        print(f"    целостность в порядке, занято {used} из {psxid.SLOTS}\n")


def main():
    parser = argparse.ArgumentParser(description="Сборка карты памяти PS1")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="показать сейвы в файлах")
    listing.add_argument("paths", nargs="+")

    make = sub.add_parser("make", help="собрать образ карты")
    make.add_argument("paths", nargs="+", help="файлы; '<файл>#<номер>' - один сейв")
    make.add_argument("-o", "--output", required=True,
                      help=".mcr/.mcd - образ, .gme - DexDrive, .vmp - PSP")
    make.add_argument("--force", action="store_true", help="перезаписать существующий")

    verify = sub.add_parser("check", help="проверить готовый образ")
    verify.add_argument("paths", nargs="+")

    args = parser.parse_args()
    if args.command == "list":
        command_list(args.paths)
    elif args.command == "make":
        command_make(args.paths, args.output, args.force)
    else:
        command_check(args.paths)


if __name__ == "__main__":
    main()
