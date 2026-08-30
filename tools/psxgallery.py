#!/usr/bin/env python3
"""Галерея сейвов PS1: обходит папку и собирает HTML со всеми находками."""

import argparse
import base64
import html
import os
import sys

import psxid
import psxstate

SCAN_EXTENSIONS = {
    ".psv", ".mcs", ".ps1", ".psx", ".mcb", ".pda", ".sav",
    ".mcr", ".mcd", ".mc", ".bin", ".gme", ".vgs", ".vmp", ".vmc",
    ".vm1", ".srm", ".ps", ".psm", ".mcx", ".ddf", ".mci", ".mem",
}

# Сейвы с PS3 часто лежат без расширения, именем служит сам код игры.
BARE_NAME = psxid.SONY_NAME

PLACEHOLDER = (
    "data:image/svg+xml;base64,"
    + base64.b64encode(
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
        b'<rect width="16" height="16" fill="none" stroke="currentColor" '
        b'stroke-opacity=".35" stroke-width="1"/></svg>'
    ).decode()
)


def collect_files(root):
    if os.path.isfile(root):
        return [root]
    found = []
    for directory, _, names in os.walk(root):
        for name in sorted(names):
            if name.startswith("."):
                continue
            extension = os.path.splitext(name)[1].lower()
            path = os.path.join(directory, name)
            if extension in SCAN_EXTENSIONS or BARE_NAME.match(name):
                found.append(path)
            elif extension != ".pic" and psxstate.read_header(path) is not None:
                found.append(path)
    return found


def icon_markup(entry):
    sprite, frames = psxid.icon_sprite(entry.get("icon") or [])
    if not sprite:
        return f'<img class="icon" src="{PLACEHOLDER}" alt="">'
    uri = "data:image/png;base64," + base64.b64encode(sprite).decode()
    if frames < 2:
        return f'<img class="icon" src="{uri}" alt="">'
    # Лента кадров едет справа налево; steps() держит покадровую смену.
    return (f'<span class="icon anim" style="background-image:url({uri});'
            f'--frames:{frames}"></span>')


def state_markup(info, source, root):
    """Карточка состояния эмулятора: миниатюра вместо иконки сейва."""
    location = os.path.relpath(source, root) if os.path.isdir(root) else os.path.basename(source)
    art = f'<img class="icon" src="{PLACEHOLDER}" alt="">'
    if info["screenshot"]:
        rows = psxstate.read_screenshot(info["screenshot"])
        if rows:
            png = psxid.write_png(psxstate.PIC_WIDTH, psxstate.PIC_HEIGHT, rows)
            uri = "data:image/png;base64," + base64.b64encode(png).decode()
            art = f'<img class="shot" src="{uri}" alt="">'
    name = info["title"] or "Неизвестная игра"
    return f"""      <article class="card state">
        <div class="art wide">{art}</div>
        <div class="meta">
          <h2>{html.escape(name)}</h2>
          <p class="internal">состояние эмулятора, слот {html.escape(info["slot"])}</p>
          <p class="serial">{html.escape(info["serial"])}</p>
          <p class="src">{html.escape(location)}</p>
        </div>
      </article>"""


def card_markup(entry, source, root):
    name = entry["title"] or entry["internal"] or "Неизвестная игра"
    location = os.path.relpath(source, root) if os.path.isdir(root) else os.path.basename(source)
    if "slot" in entry:
        location += f" · слот {entry['slot']}"

    tags = [entry["region"], f"{entry['blocks']} бл."]
    if entry.get("application"):
        tags.append("приложение PocketStation")
    if entry.get("state") == "deleted":
        tags.append("удалён")
    if entry.get("signed") is False:
        tags.append("подпись не сходится")
    if entry.get("ff8_checksum") is False:
        tags.append("CRC не сходится")

    subtitle = ""
    if entry["title"] and entry["internal"]:
        subtitle = f'<p class="internal">{html.escape(entry["internal"])}</p>'

    return f"""      <article class="card">
        <div class="art">{icon_markup(entry)}</div>
        <div class="meta">
          <h2>{html.escape(name)}</h2>
          {subtitle}
          <p class="serial">{html.escape(entry["serial"])}
             {html.escape(entry["identifier"])}</p>
          <p class="tags">{" · ".join(html.escape(t) for t in tags)}</p>
          <p class="src">{html.escape(location)}</p>
        </div>
{chocobo_markup(entry.get("chocobo"))}      </article>"""


ITEM_CLASSES = ["A", "B", "C", "D"]


def chocobo_markup(record):
    """Панель Chocobo World: то, ради чего вообще нужен PocketStation."""
    if not record:
        return ""
    stats = [
        ("уровень", str(record["level"])),
        ("HP", f'{record["hp"]}/{record["hp_max"]}'),
        ("ранг", str(record["rank"])),
        ("оружие", str(record["weapon"])),
        ("сохранений", str(record["save_count"])),
    ]
    if record["summon"]:
        stats.append(("призыв", record["summon_name"]))
    cells = "".join(
        f'<div><dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd></div>'
        for k, v in stats)

    items = "".join(
        f'<span class="item">{cls}<b>{count}</b></span>'
        for cls, count in zip(ITEM_CLASSES, record["items"]) if count)
    items = f'<p class="items">предметы: {items}</p>' if items else ""

    flags = "".join(f'<span class="flag">{html.escape(name)}</span>'
                    for name in record["flag_names"])

    warning = ""
    if record["bcd_ambiguous"]:
        warning = ('<p class="warn">числа читаются как BCD (по ChocoEdit); '
                   f'Hyne показал бы уровень {record["raw_level"]}</p>')

    return f"""        <section class="choco">
          <h3>Chocobo World <span>{html.escape(record["source"])}</span></h3>
          <dl>{cells}</dl>
          {items}
          <p class="flags">{flags}</p>
          {warning}
        </section>
"""


STYLE = """
:root {
  color-scheme: light dark;
  --bg: #f4f4f5; --panel: #ffffff; --ink: #18181b; --muted: #71717a;
  --line: #e4e4e7; --accent: #2563eb; --sunk: #fafafa; --gold: #a16207;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #0c0c0e; --panel: #17171a; --ink: #f4f4f5; --muted: #a1a1aa;
          --line: #27272a; --accent: #60a5fa; --sunk: #101013; --gold: #d4a72c; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1.5rem 4rem; background: var(--bg); color: var(--ink);
       font: 15px/1.5 ui-sans-serif, -apple-system, "Segoe UI", sans-serif; }
header { max-width: 1200px; margin: 0 auto 2rem; }
h1 { font-size: 1.35rem; margin: 0 0 .35rem; letter-spacing: -.01em; }
.lede { color: var(--muted); margin: 0; font-size: .9rem; }
.grid { max-width: 1200px; margin: 0 auto; display: grid; gap: .75rem;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.card { display: flex; flex-wrap: wrap; gap: .9rem; padding: .85rem;
        background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
.art.wide { flex: 0 0 128px; height: 96px; }
.shot { width: 128px; height: 96px; image-rendering: pixelated; display: block; }
.card.state { grid-column: span 1; }
.art { flex: 0 0 64px; height: 64px; display: grid; place-items: center;
       background: #000; border-radius: 6px; overflow: hidden; }
.icon { width: 64px; height: 64px; image-rendering: pixelated; display: block; }
.icon.anim { background-repeat: no-repeat;
             background-size: calc(var(--frames) * 64px) 64px;
             animation: play calc(var(--frames) * .18s) steps(var(--frames)) infinite; }
@keyframes play { to { background-position-x: calc(var(--frames) * -64px); } }
@media (prefers-reduced-motion: reduce) { .icon.anim { animation: none; } }
.meta { flex: 1 1 0; min-width: 0; }
h2 { font-size: .95rem; margin: 0 0 .15rem; font-weight: 600;
     overflow-wrap: anywhere; }
.internal { margin: 0 0 .3rem; font-size: .8rem; color: var(--accent);
            overflow-wrap: anywhere; }
.serial { margin: 0; font-size: .78rem; font-family: ui-monospace, Menlo, monospace;
          color: var(--muted); }
.tags { margin: .15rem 0 0; font-size: .78rem; color: var(--muted); }
.src { margin: .3rem 0 0; font-size: .72rem; color: var(--muted); opacity: .75;
       overflow-wrap: anywhere; }
.choco { flex: 1 0 100%; margin-top: .2rem; padding: .6rem .7rem;
         border: 1px solid var(--line); border-radius: 8px; background: var(--sunk); }
.choco h3 { margin: 0 0 .5rem; font-size: .78rem; text-transform: uppercase;
            letter-spacing: .06em; color: var(--gold); }
.choco h3 span { text-transform: none; letter-spacing: 0; font-weight: 400;
                 color: var(--muted); margin-left: .4rem; }
.choco dl { margin: 0; display: grid; gap: .35rem .9rem;
            grid-template-columns: repeat(auto-fit, minmax(66px, 1fr)); }
.choco dt { font-size: .68rem; color: var(--muted); text-transform: uppercase;
            letter-spacing: .04em; }
.choco dd { margin: 0; font-size: .92rem; font-weight: 600;
            font-variant-numeric: tabular-nums; }
.items { margin: .55rem 0 0; font-size: .76rem; color: var(--muted); }
.item { display: inline-block; margin-left: .35rem; padding: .05rem .35rem;
        border-radius: 4px; background: var(--line); color: var(--ink); }
.item b { margin-left: .2rem; }
.flags { margin: .45rem 0 0; display: flex; flex-wrap: wrap; gap: .25rem; }
.flag { font-size: .7rem; padding: .1rem .4rem; border-radius: 999px;
        border: 1px solid var(--gold); color: var(--gold); }
.warn { margin: .45rem 0 0; font-size: .7rem; color: var(--muted); font-style: italic; }
.problem { grid-column: 1 / -1; padding: .6rem .85rem; border-radius: 8px;
           border: 1px dashed var(--line); color: var(--muted); font-size: .82rem; }
"""


def build(root, output):
    files = collect_files(root)
    titles = psxid.load_titles(psxid.default_titles_path())

    cards, problems, saves = [], [], 0
    for path in files:
        state = psxstate.describe(path, titles)
        if state is not None:
            cards.append(state_markup(state, path, root))
            saves += 1
            continue
        try:
            entries = psxid.identify(path, titles)
        except Exception as error:  # повреждённый файл не должен ронять обход
            problems.append(f"{os.path.basename(path)}: {error}")
            continue
        for entry in entries:
            if "error" in entry:
                problems.append(f"{os.path.basename(path)}: {entry['error']}")
                continue
            cards.append(card_markup(entry, path, root))
            saves += 1

    problem_markup = ""
    if problems:
        items = "".join(f"<div class='problem'>{html.escape(p)}</div>" for p in problems)
        problem_markup = items

    page = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Сейвы PS1</title>
<style>{STYLE}</style>
</head>
<body>
  <header>
    <h1>Сейвы PS1</h1>
    <p class="lede">{saves} сохранений в {len(files)} файлах · {html.escape(root)}</p>
  </header>
  <main class="grid">
{chr(10).join(cards)}
{problem_markup}
  </main>
</body>
</html>
"""
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(page)
    return saves, len(files), problems


def main():
    parser = argparse.ArgumentParser(description="HTML-галерея сейвов PS1")
    parser.add_argument("folder")
    parser.add_argument("-o", "--output", default="saves.html")
    args = parser.parse_args()

    saves, files, problems = build(args.folder, args.output)
    print(f"{saves} сохранений из {files} файлов -> {args.output}")
    for problem in problems:
        print(f"  пропущено: {problem}", file=sys.stderr)


if __name__ == "__main__":
    main()
