#!/usr/bin/env python3
"""Сверка нового движка на Swift со старым на Python.

Перенос делается только так: пока Swift не повторит Python на всей коллекции
поле в поле, перенос не считается сделанным. Запускать из корня проекта:

    python3 tools/psxverify.py saves
"""

import argparse
import collections
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psxchronicles
import psxcrash2
import psxid
import psxpe2
import psxvagrant
import psxbuild
import psxff9
import psxfft
import psxsotn
import psxff8
import psxff8read
import psxff6
import psxff5
import psxre1
import psxff7
import psxtemplate
import psxsign
import psxconvert

BINARY = "swift/.build/debug/memcard"


TEMPLATE_INDEX = psxtemplate.by_serial()


def _counts(value):
    """Список или словарь с количествами - к виду «имя: число».

    Движки отдают одно и то же по-разному: Swift - списком записей
    `{name, used}`, Python - парами. Сравнивать надо смысл, а не форму.
    """
    if isinstance(value, dict):
        out = {}
        for key, rows in value.items():
            if isinstance(rows, list):
                out[key] = sum(
                    row.get("used", 1) if isinstance(row, dict)
                    else (row[1] if isinstance(row, (list, tuple)) and len(row) > 1
                          else 1)
                    for row in rows)
            else:
                out[key] = rows
        return dict(sorted(out.items()))
    if isinstance(value, list):
        out = {}
        for row in value:
            if isinstance(row, dict):
                out[row.get("name", "?")] = row.get("used", 0)
        return dict(sorted(out.items()))
    return {}


def vagrant_shape(got):
    """Только то, что обе стороны считают одинаково."""
    return {
        "playtime": got["playtime"],
        "hp": got["hp"],
        "mp": got["mp"],
        "map": got["map_completion"],
        "rooms": got["rooms"],
        "chests": got["chests"],
        "maxChain": got["max_chain"],
        "heals": got["heals"],
        "kills": got["kills"],
        "arts": got["arts_learned"],
        "actions": got["actions"],
        "weapons": got["weapons"],
        "stored_weapons": got["stored_weapons"],
        "learned": {k: len(v) for k, v in sorted(got["learned"].items())},
        "unopened": _counts(got["unopened"]),
        "carried": _counts(got["carried_items"]),
        "stored": _counts(got["stored_items"]),
    }


SHAPES = {"vagrant": vagrant_shape}


def python_side(root, titles):
    """Разбор старым движком: [(путь, хеш тела, поля)]."""
    rows = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            try:
                if os.path.getsize(path) < psxid.BLOCK:
                    continue
                entries = psxbuild.sources(path)
            except Exception:
                continue
            relative = os.path.relpath(path, root)
            for entry in entries:
                frame = bytearray(psxid.FRAME)
                frame[10:30] = bytes(entry["name"])
                body = b"".join(entry["blocks"])
                found = psxid.describe(bytes(frame), body, titles)
                row = {
                    "serial": found["serial"],
                    "region": found["region"],
                    "identifier": found["identifier"],
                    "blocks": len(entry["blocks"]),
                    "title": found["title"],
                    "internalName": found["internal"],
                }
                if psxff9.is_ff9(bytes(frame)):
                    row["ff9"] = canonical(as_text_counts(psxff9.overview(body)))
                if psxfft.is_fft(bytes(frame)):
                    row["fft"] = canonical(fft_shape(psxfft.overview(body)))
                if psxsotn.is_sotn(bytes(frame)):
                    row["sotn"] = canonical(sotn_shape(psxsotn.overview(body)))
                if psxvagrant.is_vagrant(bytes(frame)):
                    got = psxvagrant.overview(body)
                    if got:
                        row["vagrant"] = canonical(vagrant_shape(got))
                if psxpe2.is_pe2(bytes(frame)):
                    got = psxpe2.overview(body)
                    if got:
                        row["pe2"] = canonical(got)
                if psxcrash2.is_crash2(bytes(frame)):
                    got = psxcrash2.overview(body)
                    if got:
                        row["crash2"] = canonical(got)
                if psxchronicles.is_chronicles(bytes(frame)):
                    got = psxchronicles.overview(body)
                    if got:
                        row["chronicles"] = canonical(got)
                found_template = psxtemplate.overview(body, bytes(frame),
                                                      index=TEMPLATE_INDEX)
                if found_template:
                    row["template"] = canonical(template_shape(found_template))
                if psxff7.is_ff7(bytes(frame)):
                    row["ff7"] = canonical(ff7_shape(psxff7.overview(body)))
                if psxre1.is_re1(bytes(frame)):
                    row["re1"] = canonical(re1_shape(psxre1.overview(body)))
                if psxff5.is_ff5(bytes(frame)):
                    row["ff5"] = canonical(ff5_shape(psxff5.overview(body)))
                if psxff6.is_ff6(bytes(frame)):
                    row["ff6"] = canonical(ff6_shape(psxff6.overview(body)))
                if psxff8.is_ff8(body):
                    row["ff8"] = canonical(
                        ff8_shape(psxff8read.overview(body, found["region"])))
                rows[(relative, hashlib.sha256(body).hexdigest())] = row
    return rows


def swift_side(root, titles_path):
    if not os.path.exists(BINARY):
        raise SystemExit(f"нет {BINARY} - собрать: cd swift && swift build")
    out = subprocess.run([BINARY, "dump", titles_path, root],
                         capture_output=True, check=True).stdout
    rows = {}
    for row in json.loads(out):
        # Разбор игры лежит рядом с общими полями - сводим в один словарь,
        # чтобы сравнивать всё одним проходом.
        info = dict(row["info"])
        for game in GAMES:
            if row.get(game) is not None:
                shape = SHAPES.get(game)
                info[game] = canonical(shape(row[game]) if shape else row[game])
        rows[(row["path"], row["digest"])] = info
    return rows


# Разборщики игр, перенесённые на Swift. Список растёт по мере переноса.
GAMES = ("ff9", "fft", "sotn", "ff8", "ff6", "ff5", "re1", "ff7",
         "vagrant", "pe2", "crash2", "chronicles", "template")

FIELDS = ("serial", "region", "identifier", "blocks", "title",
          "internalName") + GAMES


def canonical(value):
    """Оба движка к одному виду: кортежи в списки, числа инвентаря в строки.

    Сверяем смысл, а не написание JSON."""
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value


def fft_shape(info):
    """Инвентарь, экипировка и даты у обоих движков к одному виду."""
    if not info:
        return info
    info["inventory"] = [[name, str(count)] for name, count in info["inventory"]]
    info["date"] = [info["date"][0], str(info["date"][1])]
    info["birthday"] = [info["birthday"][0], str(info["birthday"][1])]
    for unit in info["units"]:
        unit["gear"] = [list(g) for g in unit["gear"]]
    return info


def sotn_shape(info):
    """Счётчики и уровни фамильяров - строками, как у нового движка."""
    if not info:
        return info
    info["inventory"] = [[name, str(count)] for name, count in info["inventory"]]
    info["familiars"] = [[n, str(a), str(b)] for n, a, b in info["familiars"]]
    info["gear"] = [list(g) for g in info["gear"]]
    return info


def ff8_shape(info):
    """Счётчики и статы - к одному виду с новым движком."""
    if not info:
        return info
    info["items"] = [[name, str(count)] for name, count in info["items"]]
    for who in info["characters"]:
        who["magic"] = [[name, str(count)] for name, count in who["magic"]]
        who["stats"] = list(who["stats"])
    for gf in info["guardians"]:
        gf["learning"] = [[n, str(p), str(c)] for n, p, c in gf["learning"]]
    shown = info["playtime"].get("shown")
    info["playtime"]["shown"] = list(shown) if shown else None
    return info


def template_shape(info):
    """Значения полей - строками: JSON у нового движка типизирован."""
    if not info:
        return info
    info["fields"] = [{"name": f["name"], "value": str(f["value"]), "raw": f["raw"]}
                      for f in info["fields"]]
    return info


def ff7_shape(info):
    if not info:
        return info
    for who in info["characters"]:
        who["stats"] = list(who["stats"])
        who["hp"] = list(who["hp"])
        who["materia"] = [{"slot": s, "materia": m} for s, m in who["materia"]]
    return info


def re1_shape(info):
    if not info:
        return info
    for key in ("inventory", "container"):
        info[key] = [[name, str(qty)] for name, qty in info[key]]
    return info


def ff5_shape(info):
    if not info:
        return info
    info["inventory"] = [[name, str(count)] for name, count in info["inventory"]]
    info["playtime"] = list(info["playtime"])
    for unit in info["party"]:
        unit["gear"] = [list(g) for g in unit["gear"]]
        unit["hp"] = list(unit["hp"])
        unit["mp"] = list(unit["mp"])
    return info


def ff6_shape(info):
    if not info:
        return info
    info["inventory"] = [[name, str(count)] for name, count in info["inventory"]]
    for unit in info["party"]:
        unit["gear"] = [list(g) for g in unit["gear"]]
        unit["stats"] = list(unit["stats"])
        unit["hp"] = list(unit["hp"])
        unit["mp"] = list(unit["mp"])
    return info


def as_text_counts(info):
    if info and "inventory" in info:
        info["inventory"] = [[name, str(count)] for name, count in info["inventory"]]
    if info and "party" in info:
        for unit in info["party"]:
            unit["gear"] = [list(g) for g in unit["gear"]]
    return info


def compare(old, new):
    """Отчёт строками: что потеряно, что лишнее, что разошлось."""
    report = []
    only_old, only_new = set(old) - set(new), set(new) - set(old)
    report.append(("записей", f"старый {len(old)}, новый {len(new)}"))
    report.append(("не разобрано новым", str(len(only_old))))
    for key in sorted(only_old)[:5]:
        report.append(("", f"  {key[0]}  {old[key]['serial']}"))
    report.append(("лишнее у нового", str(len(only_new))))
    for key in sorted(only_new)[:5]:
        report.append(("", f"  {key[0]}  {new[key]['serial']}"))

    diff = collections.Counter()
    example = {}
    for key in set(old) & set(new):
        for field in FIELDS:
            if old[key].get(field) != new[key].get(field):
                diff[field] += 1
                example.setdefault(field, (key[0], old[key][field], new[key].get(field)))
    report.append(("сверено", str(len(set(old) & set(new)))))
    if not diff:
        report.append(("расхождений", "нет"))
    for field, count in diff.most_common():
        path, was, now = example[field]
        report.append((field, f"{count} расхождений"))
        report.append(("", f"  {path}"))
        report.append(("", f"  старый: {was!r}"))
        report.append(("", f"  новый:  {now!r}"))
    return report, bool(diff or only_old or only_new)


def rebuild_python(root):
    """Пересборка каждого образа старым движком: путь -> хеш и расклад."""
    rows = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            try:
                blob = open(path, "rb").read()
            except Exception:
                continue
            data, label = psxid.find_card_data(blob)
            if data is None:
                continue
            relative = os.path.relpath(path, root)
            try:
                entries = psxbuild._from_card(data, "образ")
            except Exception as error:
                rows[relative] = {"error": str(error)}
                continue
            if not entries:
                continue
            try:
                image, layout, _ = psxbuild.build(entries)
            except Exception as error:
                rows[relative] = {"error": str(error)}
                continue
            rows[relative] = {
                "digest": hashlib.sha256(image).hexdigest(),
                "saves": len(layout),
                "blocks": sum(item["blocks"] for item in layout),
            }
    return rows


def rebuild_swift(root, titles_path):
    out = subprocess.run([BINARY, "rebuild", titles_path, root],
                         capture_output=True, check=True).stdout
    rows = {}
    for row in json.loads(out):
        if row.get("error"):
            rows[row["path"]] = {"error": row["error"]}
        else:
            rows[row["path"]] = {"digest": row["digest"], "saves": row["saves"],
                                 "blocks": row["blocks"]}
    return rows


def compare_rebuild(old, new):
    report = [("пересборка карт", f"старый {len(old)}, новый {len(new)}")]
    only_old, only_new = set(old) - set(new), set(new) - set(old)
    if only_old:
        report.append(("не собрано новым", str(len(only_old))))
        for key in sorted(only_old)[:5]:
            report.append(("", f"  {key}"))
    if only_new:
        report.append(("лишнее у нового", str(len(only_new))))
    same = both = 0
    mismatch = []
    for key in set(old) & set(new):
        both += 1
        if old[key] == new[key]:
            same += 1
        else:
            mismatch.append((key, old[key], new[key]))
    report.append(("совпало байт в байт", f"{same} из {both}"))
    for key, was, now in mismatch[:5]:
        report.append(("", f"  {key}"))
        report.append(("", f"    старый: {was}"))
        report.append(("", f"    новый:  {now}"))
    return report, bool(mismatch or only_old or only_new)


def sign_python(root):
    """Подпись каждого PSV и VMP старым движком."""
    rows = {}
    # FIPS-197, приложение B - эталон, не зависящий от нашего кода.
    key = bytes(range(16))
    plain = bytes.fromhex("00112233445566778899aabbccddeeff")
    cipher = psxsign.encrypt_block(plain, key)
    rows["<FIPS-197>"] = {
        "kind": "aes",
        "ok": cipher.hex() == "69c4e0d86a7b0430d8cdb78070b4c55a"
              and psxsign.decrypt_block(cipher, key) == plain,
        "actual": cipher.hex(),
        "resigned": psxsign.decrypt_block(cipher, key).hex(),
    }
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            try:
                blob = open(path, "rb").read()
            except Exception:
                continue
            if blob[:4] not in (psxsign.PSV["magic"], psxsign.VMP["magic"]):
                continue
            try:
                found, actual, ok = psxsign.verify(blob)
                again = psxsign.resign(blob)
            except Exception:
                continue
            rows[os.path.relpath(path, root)] = {
                "kind": "psv" if blob[:4] == psxsign.PSV["magic"] else "vmp",
                "ok": ok,
                "actual": actual.hex(),
                "resigned": hashlib.sha256(again).hexdigest(),
            }
    return rows


def sign_swift(root, titles_path):
    out = subprocess.run([BINARY, "sign", titles_path, root],
                         capture_output=True, check=True).stdout
    return {row["path"]: {"kind": row["kind"], "ok": row["ok"],
                          "actual": row["actual"], "resigned": row["resigned"]}
            for row in json.loads(out)}


def compare_plain(old, new, label):
    report = [(label, f"старый {len(old)}, новый {len(new)}")]
    only_old, only_new = set(old) - set(new), set(new) - set(old)
    if only_old:
        report.append(("не сделано новым", str(len(only_old))))
        for key in sorted(only_old)[:5]:
            report.append(("", f"  {key}"))
    if only_new:
        report.append(("лишнее у нового", str(len(only_new))))
    bad = [(k, old[k], new[k]) for k in set(old) & set(new) if old[k] != new[k]]
    report.append(("совпало", f"{len(set(old) & set(new)) - len(bad)} "
                              f"из {len(set(old) & set(new))}"))
    for key, was, now in bad[:5]:
        report.append(("", f"  {key}"))
        report.append(("", f"    старый: {was}"))
        report.append(("", f"    новый:  {now}"))
    return report, bool(bad or only_old or only_new)


def convert_python(root):
    """Каждый сейв во все одиночные форматы и регионы, старым движком."""
    rows = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            try:
                if os.path.getsize(path) < psxid.BLOCK:
                    continue
                entries = psxbuild.sources(path)
            except Exception:
                continue
            relative = os.path.relpath(path, root)
            for entry in entries:
                label = psxbuild._name_of(entry["name"])
                for fmt in psxconvert.SINGLE:
                    for region in (None, "america", "europe", "japan"):
                        try:
                            blob = psxconvert.single(entry, fmt, region)
                        except Exception:
                            continue
                        key = (relative, label, fmt, region or "-")
                        rows[key] = hashlib.sha256(blob).hexdigest()
    return rows


def convert_swift(root, titles_path):
    out = subprocess.run([BINARY, "convert", titles_path, root],
                         capture_output=True, check=True).stdout
    return {(r["path"], r["name"], r["format"], r["region"]): r["digest"]
            for r in json.loads(out)}


def icons_python(root):
    """Ленты RGBA всех иконок старым движком."""
    rows = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            try:
                if os.path.getsize(path) < psxid.BLOCK:
                    continue
                entries = psxbuild.sources(path)
            except Exception:
                continue
            relative = os.path.relpath(path, root)
            for entry in entries:
                block = entry["blocks"][0]
                frames = psxid.decode_icon(block)
                if not frames:
                    continue
                # Та же лента, что у нового движка: кадры в ряд, построчно.
                sheet = b"".join(b"".join(frame[y] for frame in frames)
                                 for y in range(psxid.ICON_SIZE))
                label = psxbuild._name_of(entry["name"])
                rows[(relative, label)] = {
                    "frames": len(frames),
                    "digest": hashlib.sha256(sheet).hexdigest(),
                }
    return rows


def icons_swift(root, titles_path):
    out = subprocess.run([BINARY, "icons", titles_path, root],
                         capture_output=True, check=True).stdout
    return {(r["path"], r["name"]): {"frames": r["frames"], "digest": r["digest"]}
            for r in json.loads(out)}


def main():
    parser = argparse.ArgumentParser(description="Сверка движков Swift и Python")
    parser.add_argument("root", nargs="?", default="saves")
    args = parser.parse_args()

    titles_path = psxid.default_titles_path()
    titles = psxid.load_titles(titles_path)
    old = python_side(args.root, titles)
    new = swift_side(args.root, titles_path)
    report, failed = compare(old, new)
    for left, right in report:
        print(f"{left:<22} {right}" if left else right)

    print()
    old_cards = rebuild_python(args.root)
    new_cards = rebuild_swift(args.root, titles_path)
    card_report, card_failed = compare_rebuild(old_cards, new_cards)
    for left, right in card_report:
        print(f"{left:<22} {right}" if left else right)

    print()
    sign_report, sign_failed = compare_plain(
        sign_python(args.root), sign_swift(args.root, titles_path), "подпись")
    for left, right in sign_report:
        print(f"{left:<22} {right}" if left else right)

    print()
    icon_report, icon_failed = compare_plain(
        icons_python(args.root), icons_swift(args.root, titles_path), "иконки")
    for left, right in icon_report:
        print(f"{left:<22} {right}" if left else right)

    print()
    conv_report, conv_failed = compare_plain(
        convert_python(args.root), convert_swift(args.root, titles_path),
        "конвертация")
    for left, right in conv_report:
        print(f"{left:<22} {right}" if left else right)
    return 1 if any((failed, card_failed, sign_failed,
                     icon_failed, conv_failed)) else 0


if __name__ == "__main__":
    sys.exit(main())
