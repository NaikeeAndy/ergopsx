"""Выжимка шаблонов полей из набора game-tools-collection.

Шаблоны там написаны на TypeScript и рассчитаны на редактор: в них есть
вкладки, группы, служебные поля и заглушки, которые редактор заполняет
кодом. Нам нужен только разбор: имя поля, смещение, тип, справочник
значений и битовые разделы.

Что намеренно не берётся:

* `disabled` - редактор считает такое сам, в сейве этого нет. У CTR так
  объявлены Completion, Trophies, Boss Keys и Relics: все с нулевым
  смещением, и без отбрасывания они показывали одно и то же число.
* `hidden` - служебное.
* `overrideShift` - смещение от контейнера, которого в простом разборе
  нет. Из-за него Crash показывал «Completion Rate 130» из байта подписи.
* Разделы, где все флаги смотрят в один бит, - это заглушка под код
  редактора. У Crash так объявлены пройденные уровни: 31 флаг на одном
  бите.
* Группы Options, Sound, Config, Controller - громкость и раскладка
  кнопок не прогресс игрока.

    python3 tools/psxtemplates.py <папка game-tools-collection> [выход]
"""

import json
import pathlib
import re
import sys

SERIAL = re.compile(r"S[CL][EPU][SM][-P]?\d{5}")
SKIP_GROUPS = {"options", "sound", "config", "controller", "settings"}

# Что умеет читать psxtemplate. Строки, биты и трёхбайтовые числа
# оставлены за бортом намеренно: строку без таблицы символов игры всё
# равно не прочесть, а `bit` в шаблоне описывает отдельный флаг, для
# которого есть битовые разделы.
KNOWN_TYPES = {"uint8", "int8", "uint16", "int16", "uint32", "int32",
               "lower4", "upper4"}


def ps1_serials(text):
    """Серийники из раздела `playstation` валидатора.

    У PS2 номера выглядят так же (SLUS, SLES), и без разбора платформы
    в выжимку попадают Kingdom Hearts и TimeSplitters 2 - их смещения
    к сейвам PS1 отношения не имеют.
    """
    at = text.find("playstation:")
    if at < 0:
        return []
    # За «playstation:» может идти «playstation2:» - проверяем, что это
    # именно первый.
    if text[at:at + len("playstation2:")].startswith("playstation2:"):
        at = text.find("\n      playstation:")
        if at < 0:
            return []
    body = blocks(text, text.index("{", at))
    return sorted(set(SERIAL.findall(body)))


def blocks(text, start):
    """Кусок текста от `start` до парной закрывающей скобки."""
    depth, i = 0, start
    while i < len(text):
        if text[i] in "{[":
            depth += 1
        elif text[i] in "}]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return text[start:]


def enclosing(text, at):
    """Объект `{...}`, внутри которого стоит позиция `at`.

    Шаблон - один большой объект, поэтому делить файл на объекты
    верхнего уровня бесполезно: получается он сам. Идём от найденного
    поля наружу до ближайших парных скобок.
    """
    depth, start = 0, None
    i = at
    while i >= 0:
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
        i -= 1
    if start is None:
        return ""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return text[start:]


def group_at(text, at):
    """Название ближайшей группы или вкладки выше по тексту."""
    best = ""
    for m in re.finditer(r'name:\s*"([^"]*)",\s*\n\s*(?:flex:[^\n]*\n\s*)?'
                         r'(?:type:\s*"(?:group|tabs)")?', text[:at]):
        if m.group(1):
            best = m.group(1)
    return best


def value(chunk, key):
    """Значение поля: строка или число."""
    m = re.search(rf'\b{key}:\s*"([^"]*)"', chunk)
    if m:
        return m.group(1)
    m = re.search(rf"\b{key}:\s*(0x[0-9a-fA-F]+|\d+)", chunk)
    return int(m.group(1), 0) if m else None


def flag(chunk, key):
    return re.search(rf"\b{key}:\s*true", chunk) is not None


def parse(path):
    text = path.read_text(errors="replace")
    serials = ps1_serials(text)
    if not serials:
        return None

    fields, sections = [], []

    for m in re.finditer(r'type:\s*"variable"', text):
        chunk = enclosing(text, m.start())
        name = value(chunk, "name")
        offset = value(chunk, "offset")
        if not name or offset is None:
            continue
        if flag(chunk, "disabled") or flag(chunk, "hidden"):
            continue
        if "overrideShift" in chunk:
            continue
        if group_at(text, m.start()).lower() in SKIP_GROUPS:
            continue
        kind = value(chunk, "dataType") or "uint8"
        if kind not in KNOWN_TYPES:
            continue
        fields.append({
            "n": name,
            "o": offset,
            "t": kind,
            "b": value(chunk, "binary"),
            "r": value(chunk, "resource"),
        })

    # Длинный список флагов разбит на колонки: имя стоит только у
    # первой, продолжения идут безымянными. Их надо приклеивать к
    # предыдущему разделу, иначе теряется почти всё - у Resident Evil
    # из 129 разделов имя есть у шести.
    for m in re.finditer(r'type:\s*"bitflags"', text):
        chunk = enclosing(text, m.start())
        name = value(chunk, "name")
        if group_at(text, m.start()).lower() in SKIP_GROUPS:
            continue
        marks = re.findall(
            r"\{\s*offset:\s*(0x[0-9a-fA-F]+|\d+),\s*bit:\s*(\d+)"
            r"(?:,\s*label:\s*\"([^\"]*)\")?([^}]*)\}", chunk)
        keep = [(int(o, 0), int(b), lab or "", rest)
                for o, b, lab, rest in marks
                if "disabled: true" not in rest and "hidden: true" not in rest]
        if not keep:
            continue
        # Все флаги в одном бите - заглушка под код редактора.
        if len({(o, b) for o, b, _, _ in keep}) == 1 and len(keep) > 1:
            continue
        # Тройками, а не словарями: так их читает psxtemplate.overview.
        marks_out = [[o, b, lab] for o, b, lab, _ in keep]
        if name:
            sections.append({"n": name, "f": marks_out})
        elif sections:
            sections[-1]["f"].extend(marks_out)

    res = {}
    at = text.find("resources:")
    if at >= 0:
        body = blocks(text, text.index("{", at))
        for rname, rbody in re.findall(r"(\w+):\s*(\{[^{}]*\})", body):
            pairs = re.findall(r"(0x[0-9a-fA-F]+|\d+):\s*\"([^\"]*)\"", rbody)
            if pairs:
                res[rname] = {str(int(k, 0)): v for k, v in pairs}

    if not fields and not sections:
        return None
    return {"serials": serials, "fields": fields,
            "flags": sections, "resources": res}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    root = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2
                       else "tools/data/templates.json")

    made = {}
    for path in sorted(root.rglob("saveEditor/template.ts")):
        game = path.parent.parent.name
        got = parse(path)
        if got:
            made[game] = got

    out.write_text(json.dumps(made, ensure_ascii=False,
                              separators=(",", ":"), sort_keys=True))
    total_f = sum(len(v["fields"]) for v in made.values())
    total_s = sum(len(v["flags"]) for v in made.values())
    print(f"игр: {len(made)}, полей: {total_f}, битовых разделов: {total_s}")
    print(f"записано: {out} ({out.stat().st_size // 1024} КБ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
