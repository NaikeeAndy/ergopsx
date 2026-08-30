#!/usr/bin/env python3
"""Автопоиск наигранного времени по подписи, которую пишет сама игра.

    psxdiscover.py <папка> [--min 3]

Многие игры пишут время в подпись сейва - её видно в меню карты памяти.
Это готовый эталон: перебираем смещения и ищем поле, которое сходится
со всеми сейвами этой игры сразу. Единицы у всех разные (секунды, минуты,
кадры), поэтому проверяем каждую.

Метод даёт факт, а не догадку: если поле совпало на десяти сейвах в разных
точках прохождения, это оно и есть.
"""

import argparse
import collections
import os
import re
import struct

import psxchoco
import psxgallery
import psxid

# Подписи бывают разные: "PE−01/02:03:01/DAY2", "TIME [00:14:14]",
# "FF9/FILE01/11:13", "PE2 6:42 Refuge(2)".
TIME_PATTERNS = (
    re.compile(r"(\d+)\s*:\s*(\d{2})\s*:\s*(\d{2})"),
    re.compile(r"(\d+)\s*:\s*(\d{2})(?!\s*:)"),
)

# Множитель, на который надо умножить секунды, чтобы получить значение в поле.
UNITS = (("секунды", 1), ("минуты", 1 / 60),
         ("кадры 60 Гц", 60), ("кадры 50 Гц", 50))

WIDTHS = (("u32", 4, "<I"), ("u16", 2, "<H"))

# 99:00:00 - за этой отметкой подпись врёт, а счётчик растёт.
CAP_SECONDS = 99 * 3600


def seconds_from(text):
    for pattern in TIME_PATTERNS:
        found = pattern.search(text)
        if not found:
            continue
        parts = [int(g) for g in found.groups()]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2], True
        return parts[0] * 3600 + parts[1] * 60, False
    return None, False


def collect(root):
    """Сейвы по играм: {серийник: [(секунды, точность, блок)]}."""
    games = collections.defaultdict(list)
    for path in psxgallery.collect_files(root):
        try:
            items = psxchoco.scan(path)
        except Exception:
            continue
        for item in items:
            frame, block = item["frame"], item["block"]
            name = bytes(frame[10:30]).split(b"\x00")[0].decode("ascii", "replace")
            serial = name[2:12]
            if not re.fullmatch(r"[A-Z]{4}[-P]\d{5}", serial):
                continue
            title = psxid.decode_shift_jis(block[4:68])
            secs, exact = seconds_from(title)
            if secs is None or secs == 0:
                continue
            games[serial].append((secs, exact, bytes(block[:0x2000]), title))

    # Один и тот же сейв часто лежит в нескольких контейнерах. Дубли не просто
    # бесполезны - они ломают поиск: он требует строго различных значений.
    for serial, saves in games.items():
        unique, seen = [], set()
        for entry in saves:
            key = entry[2]
            if key in seen:
                continue
            seen.add(key)
            unique.append(entry)
        games[serial] = unique
    return games


def search(saves, tolerance_ratio=0.02):
    """Ищет (смещение, ширина, единица), сходящиеся со всеми сейвами.

    Требование различных значений проверяется только на сейвах с различным
    временем: у FF2 из Origins шестнадцать сейвов, но восемь из них показывают
    одно и то же 99:00 - счётчик упёрся в потолок подписи."""
    found = []
    length = min(len(b) for _, _, b, _ in saves)
    distinct, seen_secs = [], set()
    for index, entry in enumerate(saves):
        if entry[0] in seen_secs:
            continue
        seen_secs.add(entry[0])
        distinct.append(index)
    for label, width, fmt in WIDTHS:
        limit = 1 << (width * 8)
        for offset in range(length - width):
            values = [struct.unpack_from(fmt, b, offset)[0] for _, _, b, _ in saves]
            unique = [values[i] for i in distinct]
            if len(set(unique)) < len(unique):
                continue
            for unit, factor in UNITS:
                ok = True
                for value, (secs, exact, _, _) in zip(values, saves):
                    want = secs * factor
                    if want >= limit:
                        ok = False
                        break
                    # Поле часов в подписи двузначное и упирается в 99 -
                    # у FFT и FF8 счётчик за ним продолжает расти.
                    if secs >= CAP_SECONDS:
                        if value < CAP_SECONDS * factor:
                            ok = False
                            break
                        continue
                    # Подпись без секунд округлена до минуты - допуск шире.
                    slack = max(2.0, want * tolerance_ratio) if exact else 60 * factor + 2
                    if abs(value - want) > slack:
                        ok = False
                        break
                if ok:
                    found.append((offset, label, unit))
    return found


def leading_token(title):
    """Первое слово подписи. У Final Fantasy Origins под одним серийником
    лежат две разные игры, и различает их только оно: "FF1" или "FF2"."""
    return title.split()[0] if title.split() else ""


def search_group(saves):
    """Ищет поле по всей группе, а если не вышло - по подгруппам подписи.

    Разбиваем только при неудаче: у большинства игр первое слово подписи
    меняется от сейва к сейву (номер диска, имя героя), и дробить их незачем."""
    hits = search(saves)
    if hits:
        return [(None, hits)]
    tokens = {}
    for entry in saves:
        tokens.setdefault(leading_token(entry[3]), []).append(entry)
    if len(tokens) < 2:
        return []
    out = []
    for token, group in sorted(tokens.items()):
        if len(group) < 3:
            continue
        found = search(group)
        if found:
            out.append((token, found))
    return out


def main():
    parser = argparse.ArgumentParser(description="Автопоиск времени в сейвах")
    parser.add_argument("path")
    parser.add_argument("--min", type=int, default=3,
                        help="минимум сейвов на игру (меньше - слишком много совпадений)")
    parser.add_argument("-o", "--output",
                        help="записать найденное в json для приложения")
    args = parser.parse_args()

    titles = psxid.load_titles(psxid.default_titles_path())
    games = collect(args.path)
    print(f"игр с временем в подписи: {len(games)}\n")
    print(f"{'игра':<40} {'сейвов':>6}  найдено")
    print("-" * 78)
    total = 0
    discovered = {}
    for serial, saves in sorted(games.items(), key=lambda kv: -len(kv[1])):
        if len(saves) < args.min:
            continue
        # Приложения PocketStation в подписи пишут не наигранное время.
        if serial[4] == "P":
            continue
        name = titles.get(serial, serial)
        variants = search_group(saves)
        if not variants:
            print(f"{name[:40]:<40} {len(saves):>6}  —")
            continue
        total += 1
        records = []
        for token, hits in variants:
            offset, width, unit = hits[0]
            record = {"game": name, "offset": offset, "width": width,
                      "unit": unit, "saves": len(saves)}
            if token:
                record["match"] = token
            records.append(record)
            extra = f" (+{len(hits) - 1} других)" if len(hits) > 1 else ""
            label = f"{name} [{token}]" if token else name
            print(f"{label[:40]:<40} {len(saves):>6}  "
                  f"{offset:#06x} {width} {unit}{extra}")
        discovered[serial] = records[0] if len(records) == 1 else records
    print(f"\nполе времени найдено у {total} игр")
    if args.output:
        import json
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(discovered, fh, ensure_ascii=False, indent=1)
        print(f"записано: {args.output}")


if __name__ == "__main__":
    main()
