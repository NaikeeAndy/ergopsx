"""Названия действий Vagrant Story из декомпиляции.

Таблица `vs_main_actions[]` лежит исходным кодом в `src/SLUS_010.40/main.c`
проекта `ser-pounce/rood-reverse` (CC0) - там и имена, и вид действия.
Из образа диска её доставать не нужно.

В сейве по `0x640` лежат 32 байта: по биту на каждое из 256 действий,
и бит внутри байта считается **со старшего** - `0x80 >> (i & 7)`, как в
`INITBTL.PRG/18.c`. С младшего список поедет и покажет чужие названия.

    python3 tools/psxvsactions.py <main.c> [выход.json]
"""

import json
import pathlib
import re
import sys

# Виды действий из `enum actionTypes`. Показываем только те, что
# осваивает игрок: удары монстров и ловушки ему не принадлежат.
KINDS = {1: "spell", 2: "ability", 3: "breakArt"}


def clean(name):
    """Имя из декомпиляции: хвост из нулей и управляющие в виде |>6|."""
    text = name.split("\\000")[0]
    # Кернинг между словами - пробел.
    text = re.sub(r"\|>(\d+)\|", " ", text)
    text = re.sub(r"\|[^|]*\|", "", text)
    return " ".join(text.split())


def parse(path):
    source = path.read_text(errors="replace")
    at = source.index("vs_action_t vs_main_actions[]")
    chunks = re.split(r"\{\s*\.id = ", source[at:])[1:]

    out = []
    for chunk in chunks[:256]:
        name = re.search(r'\.name = "([^"]*)"', chunk)
        kind = re.search(r"\.type = (\d+)", chunk)
        shown = clean(name.group(1)) if name else ""
        if shown == "untitled":
            shown = ""
        out.append({"n": shown,
                    "k": KINDS.get(int(kind.group(1)) if kind else 0, "")})
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    actions = parse(pathlib.Path(sys.argv[1]))
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2
                       else "tools/data/vagrant-map.json")
    saved = json.loads(out.read_text()) if out.exists() else {}
    saved["actions"] = actions
    out.write_text(json.dumps(saved, ensure_ascii=False, indent=1))

    named = sum(1 for a in actions if a["n"])
    print(f"действий: {len(actions)}, с именами: {named}")
    for key, title in (("spell", "заклинаний"), ("ability", "способностей"),
                       ("breakArt", "приёмов оружия")):
        print(f"  {title}: {sum(1 for a in actions if a['k'] == key)}")
    print(f"записано: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
