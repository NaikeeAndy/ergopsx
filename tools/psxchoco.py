#!/usr/bin/env python3
"""Перенос Chocobo World: из дампа PocketStation в сейв Final Fantasy VIII.

    psxchoco.py show   <файл>...                    что за Боко в файле
    psxchoco.py copy   <откуда> <сейв FF8> [-o ...]  пересадить Боко

Источником может быть дамп PocketStation, образ карты, .mcs или .psv.
Приёмником - сейв FF8 в виде .psv, .mcs или блока. Контрольная сумма FF8
и подпись PSV пересчитываются автоматически.
"""

import argparse
import os
import sys

import psxff8
import psxid
import psxpocket
import psxsign


def _synthetic_frame(path):
    """У одиночных сейвов каталожного фрейма нет - собираем минимальный.

    Имя файла берём не целиком: у выгрузок оно длинное
    ("castlevania-...-BASLUS-00067DRAX00.srm"), и первые 20 символов кода игры
    не содержат. Ищем код регуляркой, как это делает распознаватель."""
    stem = os.path.splitext(os.path.basename(path))[0]
    found = psxid.EMBEDDED_NAME.search(stem)
    name = (found.group(0) if found else stem).encode("ascii", errors="replace")[:20]
    frame = bytearray(psxid.FRAME)
    frame[0] = 0x51
    frame[10:10 + len(name)] = name
    return bytes(frame)


def _frame_from_name(name):
    """Минимальный каталожный фрейм с готовым 20-байтовым именем."""
    frame = bytearray(psxid.FRAME)
    frame[0] = 0x51
    frame[10:30] = bytes(name)[:20].ljust(20, b"\x00")
    return bytes(frame)


def load_blocks(path):
    """Возвращает [(описание, блок сейва, каталожный фрейм)] из любого файла.

    Фрейм нужен именно настоящий: по нему опознаются приложения PocketStation,
    а поддельный из имени файла для карт не годится."""
    return [(item["where"], item["block"], item["frame"]) for item in scan(path)]


def scan(path):
    """То же, но со смещением блока в файле - чтобы можно было записать обратно."""
    with open(path, "rb") as fh:
        blob = fh.read()

    if blob[:4] == psxsign.PSV["magic"]:
        # Имя сейва лежит в заголовке PSV по 0x64. Раньше оно бралось из имени
        # файла - у настоящих выгрузок с PS3 они совпадают, но у собранного
        # нами файла имя может быть любым.
        return [{"where": "сейв PSV", "block": psxsign.save_block(blob),
                 "frame": _frame_from_name(bytes(blob[0x64:0x78])),
                 "offset": None, "blob": blob, "kind": "psv"}]
    if blob[:1] == b"Q":
        return [{"where": "сейв MCS", "block": blob[psxid.FRAME:],
                 "frame": blob[:psxid.FRAME], "offset": psxid.FRAME, "blob": blob,
                 "kind": "plain"}]
    if blob[:2] in (b"SC", b"sc"):
        return [{"where": "сейв без заголовка", "block": blob,
                 "frame": _synthetic_frame(path), "offset": 0, "blob": blob,
                 "kind": "plain"}]

    base = psxid.card_offset(blob)
    data, label = psxid.find_card_data(blob)
    if data is None or base is None:
        raise ValueError(f"{os.path.basename(path)}: формат не распознан")

    found = []
    for slot in range(psxid.SLOTS):
        frame = data[psxid.FRAME * (slot + 1):psxid.FRAME * (slot + 2)]
        _, is_head = psxid.SLOT_STATES.get(frame[0], ("corrupt", False))
        if not is_head:
            continue
        offset = base + psxid.BLOCK * (slot + 1)
        found.append({"where": f"{label}, слот {slot + 1}",
                      "block": blob[offset:offset + psxid.BLOCK * 15],
                      "frame": frame, "offset": offset, "blob": blob,
                      "kind": "plain"})
    return found


def write_back(item, block, path):
    """Кладёт изменённый блок обратно в контейнер и пишет файл."""
    if item["kind"] == "psv":
        result = psxsign.replace_block(item["blob"], block)
    else:
        blob = bytearray(item["blob"])
        blob[item["offset"]:item["offset"] + len(block)] = block
        result = bytes(blob)
    with open(path, "wb") as fh:
        fh.write(result)
    return result


def _pocket_base(block):
    """Смещение свежего банка внутри сейва Chocobo World."""
    live = [(psxpocket.read_record(block, base), base)
            for base in psxpocket.POCKET_BANKS]
    live = [pair for pair in live if psxpocket.plausible(pair[0])]
    return max(live, key=lambda pair: pair[0]["save_count"])[1]


def find_source_record(path):
    """Ищет запись Chocobo World: (описание, 64 байта, разбор)."""
    return [(item["where"], record_bytes, record)
            for item, base, record_bytes, record in _located(path)]


def _located(path):
    """[(элемент scan, смещение записи в блоке, 64 байта, разбор)]"""
    out = []
    for item in scan(path):
        record = psxpocket.find_chocobo(item["block"], item["frame"])
        if not record:
            continue
        base = (psxff8.CHOCOBO_OFFSET if record["source"].startswith("блок")
                else _pocket_base(item["block"]))
        out.append((item, base, bytes(item["block"][base:base + 64]), record))
    return out


def command_show(paths):
    for path in paths:
        print(os.path.basename(path))
        try:
            found = find_source_record(path)
        except ValueError as error:
            print(f"    ! {error}")
            continue
        if not found:
            print("    Chocobo World не найден")
        for where, _, record in found:
            print(f"    {where}: {psxpocket.summary(record)}")
            print(f"      {record['source']}, сохранений {record['save_count']}")
            if record["flag_names"]:
                print(f"      {', '.join(record['flag_names'])}")
        print()


def command_copy(source, target, output):
    found = find_source_record(source)
    if not found:
        sys.exit(f"в '{source}' нет данных Chocobo World")
    if len(found) > 1:
        print("найдено несколько записей, беру самую свежую:", file=sys.stderr)
        for where, _, record in found:
            print(f"  {where}: сохранений {record['save_count']}", file=sys.stderr)
    where, record_bytes, record = max(found, key=lambda f: f[2]["save_count"])
    print(f"источник: {where} — {psxpocket.summary(record)}")

    with open(target, "rb") as fh:
        blob = fh.read()

    is_psv = blob[:4] == psxsign.PSV["magic"]
    block = psxsign.save_block(blob) if is_psv else (
        blob[psxid.FRAME:] if blob[:1] == b"Q" else blob)

    if not psxff8.is_ff8(block):
        sys.exit(f"'{target}' — не сейв Final Fantasy VIII")

    before = psxpocket.read_record(block, psxff8.CHOCOBO_OFFSET)
    if before and psxpocket.plausible(before):
        print(f"было в сейве: {psxpocket.summary(before)}")

    patched = psxff8.transplant_chocobo(block, record_bytes)
    assert psxff8.verify(patched)[3], "контрольная сумма FF8 не сошлась"

    if is_psv:
        result = psxsign.replace_block(blob, patched)
        assert psxsign.verify(result)[2], "подпись PSV не сошлась"
        note = "контрольная сумма FF8 и подпись PSV пересчитаны"
    elif blob[:1] == b"Q":
        result = blob[:psxid.FRAME] + patched
        note = "контрольная сумма FF8 пересчитана"
    else:
        result = patched
        note = "контрольная сумма FF8 пересчитана"

    output = output or _default_output(target)
    with open(output, "wb") as fh:
        fh.write(result)
    print(f"стало:        {psxpocket.summary(record)}")
    print(f"записано: {output} ({note})")


def command_link(chocobo_path, ff8_path, away, dry_run):
    """Привязывает сейв Chocobo World к конкретному сейву FF8.

    Ни один из двух существующих редакторов не делает обе половины: ChocoEdit
    ставит FF8ID, но флаг отлучки у него закомментирован, а hyne правит флаги,
    но associatedSaveID и home_walking не трогает вовсе."""
    sources = [entry for entry in _located(chocobo_path)
               if not entry[3]["source"].startswith("блок")]
    if not sources:
        sys.exit(f"в '{chocobo_path}' нет сейва Chocobo World")
    choco_item, choco_base, choco_record, choco_parsed = max(
        sources, key=lambda e: e[3]["save_count"])

    targets = [entry for entry in _located(ff8_path)
               if entry[3]["source"].startswith("блок")]
    if not targets:
        # Сейв FF8 может быть и без осмысленной записи Chocobo - берём его как есть.
        targets = [(item, psxff8.CHOCOBO_OFFSET,
                    bytes(item["block"][psxff8.CHOCOBO_OFFSET:
                                        psxff8.CHOCOBO_OFFSET + 64]), None)
                   for item in scan(ff8_path) if psxff8.is_ff8(item["block"])]
    if not targets:
        sys.exit(f"'{ff8_path}' — не сейв Final Fantasy VIII")
    ff8_item, ff8_base, ff8_record, _ = targets[0]

    token = psxpocket.read_link(ff8_record)
    print(f"Chocobo World: {choco_item['where']} — {psxpocket.summary(choco_parsed)}")
    print(f"сейв FF8:      {ff8_item['where']}")
    print(f"метка привязки в сейве FF8: {token:08X}")
    print(f"было у Боко:                {psxpocket.read_link(choco_record):08X}")
    if token == 0:
        print("внимание: метка нулевая — сейв FF8 ещё ни с кем не связывался")
    print()
    _show_flags("было у Боко ", choco_record)
    _show_flags("было в FF8  ", ff8_record)

    new_choco = psxpocket.with_link(choco_record, token)
    new_ff8 = ff8_record
    if away:
        # Бит 0 включает Chocobo World, бит 1 отправляет Боко в отлучку.
        # Без первого игра считает мини-игру не активированной и связку
        # игнорирует, сколько ни ставь второй.
        new_choco = psxpocket.with_flags(new_choco, enabled=True, away=True)
        new_ff8 = psxpocket.with_flags(new_ff8, enabled=True, away=True,
                                       walking=False)
        print("с обеих сторон: Chocobo World включён, Боко в отлучке, "
              "home_walking сброшен")
    _show_flags("стало у Боко", new_choco)
    _show_flags("стало в FF8 ", new_ff8)
    print()

    if dry_run:
        print("(--dry-run: ничего не записано)")
        return

    choco_block = bytearray(choco_item["block"])
    choco_block[choco_base:choco_base + 64] = new_choco
    choco_out = _default_output(chocobo_path, "-linked")
    write_back(choco_item, bytes(choco_block), choco_out)

    ff8_block = psxff8.transplant_chocobo(ff8_item["block"], new_ff8)
    assert psxff8.verify(ff8_block)[3], "контрольная сумма FF8 не сошлась"
    ff8_out = _default_output(ff8_path, "-linked")
    result = write_back(ff8_item, ff8_block, ff8_out)
    if ff8_item["kind"] == "psv":
        assert psxsign.verify(result)[2], "подпись PSV не сошлась"

    print(f"записано: {choco_out}")
    print(f"записано: {ff8_out}")


def _show_flags(label, record_bytes):
    names = [name for bit, name in psxpocket.MOG_FLAGS if record_bytes[0] & bit]
    print(f"  {label}: {record_bytes[0]:08b}"
          + (f" — {', '.join(names)}" if names else " — флагов нет"))


def _default_output(target, suffix="-boko"):
    stem, extension = os.path.splitext(target)
    return f"{stem}{suffix}{extension}"


def main():
    parser = argparse.ArgumentParser(description="Перенос Chocobo World")
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="показать Боко в файлах")
    show.add_argument("files", nargs="+")

    copy = sub.add_parser("copy", help="пересадить Боко в сейв FF8")
    copy.add_argument("source", help="дамп PocketStation, карта или сейв")
    copy.add_argument("target", help="сейв Final Fantasy VIII")
    copy.add_argument("-o", "--output", help="куда писать (по умолчанию рядом, с -boko)")

    link = sub.add_parser("link", help="привязать Chocobo World к сейву FF8")
    link.add_argument("chocobo", help="карта или сейв с Chocobo World")
    link.add_argument("ff8", help="сейв Final Fantasy VIII")
    link.add_argument("--no-away", action="store_true",
                      help="не трогать флаг отлучки")
    link.add_argument("--dry-run", action="store_true", help="только показать")

    args = parser.parse_args()
    if args.command == "show":
        command_show(args.files)
    elif args.command == "copy":
        command_copy(args.source, args.target, args.output)
    else:
        command_link(args.chocobo, args.ff8, not args.no_away, args.dry_run)


if __name__ == "__main__":
    main()
