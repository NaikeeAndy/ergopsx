#!/usr/bin/env python3
"""Визуальный разбор сейва Final Fantasy Tactics.

    psxfftview.py <файл или папка> [-o out.html] [--grind]

Показывает отряд, классы, экипировку, экранные и сырые статы, инвентарь.
С --grind считает ещё и план паверлевелинга на каждого бойца - это медленно,
потому что план проверяется точной симуляцией, а не приближением.
"""

import argparse
import html
import os
import sys

import psxchoco
import psxfft
import psxfftgrind as grind
import psxfftstats as stats
import psxgallery

STYLE = """
:root {
  color-scheme: light dark;
  --bg: #f4f4f5; --panel: #fff; --sunk: #fafafa; --ink: #18181b;
  --muted: #71717a; --line: #e4e4e7; --accent: #2563eb; --gold: #a16207;
  --bar: #d4d4d8; --good: #16a34a;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #0c0c0e; --panel: #17171a; --sunk: #101013; --ink: #f4f4f5;
          --muted: #a1a1aa; --line: #27272a; --accent: #60a5fa; --gold: #d4a72c;
          --bar: #27272a; --good: #4ade80; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1.5rem 4rem; background: var(--bg); color: var(--ink);
       font: 15px/1.5 ui-sans-serif, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1240px; margin: 0 auto; }
h1 { font-size: 1.35rem; margin: 0 0 .3rem; letter-spacing: -.01em; }
.lede { color: var(--muted); margin: 0 0 .4rem; font-size: .9rem; }
.facts { display: flex; flex-wrap: wrap; gap: .4rem 1.4rem; margin: 0 0 2rem;
         font-size: .85rem; color: var(--muted); }
.facts b { color: var(--ink); font-variant-numeric: tabular-nums; }
h2 { font-size: .78rem; text-transform: uppercase; letter-spacing: .07em;
     color: var(--muted); margin: 2rem 0 .8rem; font-weight: 600; }
.grid { display: grid; gap: .75rem;
        grid-template-columns: repeat(auto-fill, minmax(370px, 1fr)); }
.unit { background: var(--panel); border: 1px solid var(--line);
        border-radius: 10px; padding: .85rem .95rem; }
.uhead { display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap; }
.uname { font-weight: 600; font-size: 1rem; }
.ujob { color: var(--accent); font-size: .85rem; }
.ulv { margin-left: auto; font-size: .8rem; color: var(--muted);
       font-variant-numeric: tabular-nums; }
.tags { margin: .3rem 0 .6rem; font-size: .74rem; color: var(--muted); }
.screen { display: grid; grid-template-columns: repeat(5, 1fr); gap: .3rem;
          margin: .5rem 0 .7rem; }
.screen div { background: var(--sunk); border-radius: 6px; padding: .3rem .1rem;
              text-align: center; }
.screen dt { font-size: .62rem; text-transform: uppercase; color: var(--muted);
             letter-spacing: .04em; }
.screen dd { margin: .1rem 0 0; font-size: 1rem; font-weight: 600;
             font-variant-numeric: tabular-nums; }
.screen dd.max { color: var(--good); }
.bars { margin: 0 0 .6rem; }
.bar { display: grid; grid-template-columns: 68px 1fr 42px; align-items: center;
       gap: .4rem; font-size: .7rem; color: var(--muted); margin: .16rem 0; }
.track { display: block; height: 6px; background: var(--bar);
         border-radius: 3px; overflow: hidden; }
.fill { display: block; height: 100%; background: var(--accent); }
.fill.done { background: var(--good); }
.pct { text-align: right; font-variant-numeric: tabular-nums; }
.gear { font-size: .76rem; color: var(--muted); margin: 0 0 .2rem; }
.gear b { color: var(--ink); font-weight: 500; }
.plan { margin-top: .7rem; padding: .55rem .65rem; border-radius: 8px;
        background: var(--sunk); border: 1px solid var(--line); font-size: .78rem; }
.plan h3 { margin: 0 0 .35rem; font-size: .68rem; text-transform: uppercase;
           letter-spacing: .06em; color: var(--gold); }
.plan ol { margin: 0; padding-left: 1.1rem; }
.plan .none { color: var(--good); }
table { border-collapse: collapse; width: 100%; font-size: .82rem; }
th, td { text-align: left; padding: .28rem .6rem .28rem 0; }
th { font-size: .68rem; text-transform: uppercase; letter-spacing: .05em;
     color: var(--muted); font-weight: 600; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.cols { column-width: 210px; column-gap: 1.6rem; font-size: .82rem; }
.cols div { break-inside: avoid; display: flex; justify-content: space-between;
            gap: .6rem; padding: .1rem 0; }
.cols span { color: var(--muted); font-variant-numeric: tabular-nums; }
.missing { color: var(--muted); font-size: .82rem; line-height: 1.7; }
.missing b { color: var(--ink); font-weight: 500; }
"""


def bar(label, raw, cap):
    pct = min(100, raw * 100 // cap) if cap else 0
    done = " done" if raw >= cap else ""
    return (f'<div class="bar"><span>{html.escape(label)}</span>'
            f'<span class="track"><span class="fill{done}" style="width:{pct}%"></span></span>'
            f'<span class="pct">{pct}%</span></div>')


def unit_card(unit, plan, caps):
    tags = " · ".join(x for x in (unit["who"], unit["gender"], unit["zodiac"],
                                  "гость" if unit["guest"] else "",
                                  unit["status"]) if x)
    screen = ""
    if unit["stats"]:
        cells = []
        for key in stats.STATS:
            top = {"hp": 999, "mp": 999, "sp": 50, "pa": 99, "ma": 99}[key]
            klass = " class='max'" if unit["stats"][key] >= top else ""
            cells.append(f'<div><dt>{stats.STAT_LABELS[key]}</dt>'
                         f'<dd{klass}>{unit["stats"][key]}</dd></div>')
        screen = f'<dl class="screen">{"".join(cells)}</dl>'

    bars = "".join(bar(stats.STAT_LABELS[k], unit["raw_stats"][k], caps[k])
                   for k in stats.STATS)

    gear = ""
    if unit["gear"]:
        gear = ('<p class="gear">' + " · ".join(
            f'{html.escape(slot)}: <b>{html.escape(name)}</b>'
            for slot, name in unit["gear"]) + "</p>")

    block = ""
    if plan is not None:
        if isinstance(plan, str):
            body = f'<p class="none">{html.escape(plan)}</p>'
        elif not plan["blocks"]:
            body = '<p class="none">все статы на потолке, гринд не нужен</p>'
        else:
            steps = "".join(f"<li>{c} × подъём {html.escape(n)}</li>"
                            for n, c in plan["blocks"])
            body = (f'<ol>{steps}</ol>'
                    f'<p>спуск в классе {html.escape(plan["down"])}, '
                    f'всего {plan["total"]} циклов</p>')
        block = f'<div class="plan"><h3>план гринда</h3>{body}</div>'

    return f"""      <article class="unit">
        <div class="uhead">
          <span class="uname">{html.escape(unit['name'] or '—')}</span>
          <span class="ujob">{html.escape(unit['job'])}</span>
          <span class="ulv">ур. {unit['level']} · храбр {unit['brave']} · вера {unit['faith']}</span>
        </div>
        <p class="tags">{html.escape(tags)}</p>
        {screen}
        <div class="bars">{bars}</div>
        {gear}
        {block}
      </article>"""


def build(info, block, with_grind, data):
    caps = data["functional_raw_caps"]
    plans = {}
    if with_grind:
        for index, unit in enumerate(info["units"]):
            if not unit["stats"]:
                plans[index] = ("монстр — класс один, гринд неприменим"
                                if unit["is_monster"]
                                else "класса нет в справочнике роста")
                continue
            print(f"  считаю план: {unit['name']} ({index+1}/{len(info['units'])})",
                  file=sys.stderr)
            found = grind.solve(unit["raw_stats"], unit["gender"],
                                data=data, limit=30, owner=unit["who"])
            plans[index] = (found if found is not None
                            else "решение не найдено в пределах перебора")

    cards = "\n".join(unit_card(u, plans.get(i), caps)
                      for i, u in enumerate(info["units"]))

    inventory = "".join(
        f"<div>{html.escape(n)}<span>×{c}</span></div>" for n, c in info["inventory"])
    absent = psxfft.absent_items(block)
    missing = " · ".join(f"<b>{html.escape(n)}</b>" for n in absent)

    hours, minutes, seconds = info["playtime"]
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Final Fantasy Tactics — {html.escape(info['name'])}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
  <h1>Final Fantasy Tactics</h1>
  <p class="lede">{html.escape(info['name'])} · {html.escape(info['job'])} ·
     уровень {info['level']}</p>
  <p class="facts">
    <span>наиграно <b>{hours}:{minutes:02d}:{seconds:02d}</b></span>
    <span>казна <b>{f"{info['funds']:,}".replace(",", " ")}</b> гил</span>
    <span>место <b>{html.escape(info['location'])}</b></span>
    <span>дата <b>{info['date'][1]} {html.escape(info['date'][0])}</b></span>
    <span>отряд <b>{len(info['units'])}</b></span>
  </p>

  <h2>Отряд</h2>
  <div class="grid">
{cards}
  </div>

  <h2>Инвентарь — {len(info['inventory'])} позиций</h2>
  <div class="cols">{inventory}</div>

  <h2>Нет ни на складе, ни на бойцах — {len(absent)}</h2>
  <p class="missing">{missing}</p>
</div>
</body>
</html>
"""


def pick_save(path):
    """Из файла или папки берёт сейв FFT с наибольшим временем."""
    best = None
    paths = ([path] if os.path.isfile(path) else psxgallery.collect_files(path))
    for candidate in paths:
        try:
            items = psxchoco.scan(candidate)
        except Exception:
            continue
        for item in items:
            if not psxfft.is_fft(item["frame"]):
                continue
            info = psxfft.overview(item["block"])
            if info and (best is None or
                         info["playtime_raw"] > best[0]["playtime_raw"]):
                best = (info, item["block"], candidate)
    return best


def main():
    parser = argparse.ArgumentParser(description="Визуальный разбор сейва FFT")
    parser.add_argument("path", help="файл сейва или папка с сейвами")
    parser.add_argument("-o", "--output", default="fft.html")
    parser.add_argument("--grind", action="store_true",
                        help="посчитать план паверлевелинга (небыстро)")
    args = parser.parse_args()

    found = pick_save(args.path)
    if not found:
        sys.exit("сейвов Final Fantasy Tactics не найдено")
    info, block, source = found
    print(f"взят сейв: {os.path.basename(source)} — {info['name']}, "
          f"{info['playtime'][0]} ч", file=sys.stderr)

    page = build(info, block, args.grind, stats.load())
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"{len(info['units'])} бойцов, {len(info['inventory'])} позиций "
          f"-> {args.output}")


if __name__ == "__main__":
    main()
