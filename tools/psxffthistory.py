#!/usr/bin/env python3
"""История роста статов по всем сейвам Final Fantasy Tactics.

    psxffthistory.py <папка> [-o out.html] [--who Ramza Orlandu ...]

Собирает все сейвы, выстраивает по наигранному времени и рисует, как менялись
сырые статы. Циклы паверлевелинга видны как обрывы: боец падает на 1 уровень,
статы обваливаются, потом отрастают выше прежнего.
"""

import argparse
import html
import os

import psxchoco
import psxfft
import psxfftstats as stats
import psxgallery

WIDTH, HEIGHT = 720, 210
PAD_L, PAD_R, PAD_T, PAD_B = 44, 12, 14, 26

COLORS = {"hp": "#ef4444", "mp": "#3b82f6", "sp": "#22c55e",
          "pa": "#f59e0b", "ma": "#a855f7"}

STYLE = """
:root { color-scheme: light dark;
  --bg:#f4f4f5; --panel:#fff; --ink:#18181b; --muted:#71717a; --line:#e4e4e7; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0c0c0e; --panel:#17171a; --ink:#f4f4f5; --muted:#a1a1aa; --line:#27272a; } }
* { box-sizing: border-box; }
body { margin:0; padding:2rem 1.5rem 4rem; background:var(--bg); color:var(--ink);
       font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",sans-serif; }
.wrap { max-width:840px; margin:0 auto; }
h1 { font-size:1.35rem; margin:0 0 .3rem; }
.lede { color:var(--muted); margin:0 0 2rem; font-size:.9rem; }
section { background:var(--panel); border:1px solid var(--line); border-radius:10px;
          padding:.9rem 1rem 1.1rem; margin-bottom:1rem; }
h2 { font-size:1rem; margin:0 0 .1rem; }
.sub { color:var(--muted); font-size:.8rem; margin:0 0 .6rem; }
.legend { display:flex; flex-wrap:wrap; gap:.1rem .9rem; font-size:.72rem;
          color:var(--muted); margin:.2rem 0 .5rem; }
.legend b { font-weight:500; }
.dot { display:inline-block; width:8px; height:8px; border-radius:2px;
       margin-right:.3rem; vertical-align:-1px; }
svg { display:block; width:100%; height:auto; overflow:visible; }
.axis { stroke:var(--line); stroke-width:1; }
.tick { fill:var(--muted); font-size:9px; }
.drop { stroke:var(--muted); stroke-width:1; stroke-dasharray:2 3; opacity:.7; }
table { border-collapse:collapse; width:100%; font-size:.76rem; margin-top:.5rem; }
th,td { padding:.16rem .5rem .16rem 0; text-align:right; }
th:first-child, td:first-child { text-align:left; }
th { color:var(--muted); font-weight:600; font-size:.66rem; text-transform:uppercase; }
td { font-variant-numeric:tabular-nums; }
"""


def collect(root):
    """Сейвы по уникальному времени: дубли одного сейва на разных картах не нужны."""
    seen = {}
    for path in psxgallery.collect_files(root):
        try:
            items = psxchoco.scan(path)
        except Exception:
            continue
        for item in items:
            if not psxfft.is_fft(item["frame"]):
                continue
            info = psxfft.overview(item["block"])
            if info and info["playtime_raw"] not in seen:
                seen[info["playtime_raw"]] = (os.path.basename(path), info)
    return sorted(seen.items())


def series(points, who):
    """[(часы, уровень, класс, raw-статы)] по одному бойцу."""
    out = []
    for secs, (_, info) in points:
        matches = [u for u in info["units"] if u["name"] == who]
        if not matches:
            continue
        # У сюжетных бойцов в отряде бывает две записи - берём прокачанную.
        unit = max(matches, key=lambda u: sum(u["raw_stats"].values()))
        out.append((secs / 3600, unit["level"], unit["job"], unit["raw_stats"]))
    return out


def chart(rows, caps):
    if len(rows) < 2:
        return "<p class='sub'>слишком мало точек для графика</p>"
    xs = [r[0] for r in rows]
    x0, x1 = min(xs), max(xs)
    span = (x1 - x0) or 1

    def px(hours):
        return PAD_L + (hours - x0) / span * (WIDTH - PAD_L - PAD_R)

    def py(fraction):
        return PAD_T + (1 - min(1.0, fraction)) * (HEIGHT - PAD_T - PAD_B)

    parts = [f'<line class="axis" x1="{PAD_L}" y1="{py(0)}" '
             f'x2="{WIDTH - PAD_R}" y2="{py(0)}"/>']
    for frac, label in ((0, "0"), (0.5, "50%"), (1, "100%")):
        y = py(frac)
        parts.append(f'<line class="axis" x1="{PAD_L}" y1="{y}" '
                     f'x2="{WIDTH - PAD_R}" y2="{y}" opacity=".4"/>')
        parts.append(f'<text class="tick" x="{PAD_L - 6}" y="{y + 3}" '
                     f'text-anchor="end">{label}</text>')

    # Отметки, где боец оказался на первом уровне - это дно цикла.
    for hours, level, _, _ in rows:
        if level == 1:
            parts.append(f'<line class="drop" x1="{px(hours):.1f}" y1="{PAD_T}" '
                         f'x2="{px(hours):.1f}" y2="{py(0)}"/>')

    for stat in stats.STATS:
        pts = " ".join(f"{px(h):.1f},{py(raw[stat] / caps[stat]):.1f}"
                       for h, _, _, raw in rows)
        parts.append(f'<polyline fill="none" stroke="{COLORS[stat]}" '
                     f'stroke-width="1.8" stroke-linejoin="round" points="{pts}"/>')

    step = max(1, round(span / 6))
    tick = int(x0 // step * step)
    while tick <= x1:
        if tick >= x0:
            parts.append(f'<text class="tick" x="{px(tick):.1f}" '
                         f'y="{py(0) + 14}" text-anchor="middle">{tick} ч</text>')
        tick += step
    return (f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" '
            f'preserveAspectRatio="none">{"".join(parts)}</svg>')


def table(rows, caps):
    head = "".join(f"<th>{stats.STAT_LABELS[s]}</th>" for s in stats.STATS)
    body = []
    for hours, level, job, raw in rows:
        cells = "".join(f"<td>{raw[s] * 100 // caps[s]}%</td>" for s in stats.STATS)
        body.append(f"<tr><td>{int(hours)}:{int(hours % 1 * 60):02d}</td>"
                    f"<td>{level}</td><td>{html.escape(job[:18])}</td>{cells}</tr>")
    return (f"<table><tr><th>время</th><th>ур</th><th>класс</th>{head}</tr>"
            + "".join(body) + "</table>")


def build(points, watch, caps):
    legend = "".join(
        f'<span><i class="dot" style="background:{COLORS[s]}"></i>'
        f'<b>{stats.STAT_LABELS[s]}</b></span>' for s in stats.STATS)
    blocks = []
    for who in watch:
        rows = series(points, who)
        if not rows:
            blocks.append(f"<section><h2>{html.escape(who)}</h2>"
                          f"<p class='sub'>в сейвах не найден</p></section>")
            continue
        drops = sum(1 for _, level, _, _ in rows if level == 1)
        blocks.append(
            f"<section><h2>{html.escape(who)}</h2>"
            f"<p class='sub'>{len(rows)} точек · "
            f"{rows[0][0]:.0f}–{rows[-1][0]:.0f} ч · "
            f"спусков на 1 уровень видно: {drops}</p>"
            f'<div class="legend">{legend}</div>'
            f"{chart(rows, caps)}{table(rows, caps)}</section>")

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FFT — история статов</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
  <h1>Final Fantasy Tactics — как росли статы</h1>
  <p class="lede">Сырые значения в процентах от функционального потолка.
     Пунктир — момент, когда боец оказался на первом уровне: это дно цикла
     паверлевелинга.</p>
{"".join(blocks)}
</div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="История статов FFT по всем сейвам")
    parser.add_argument("path")
    parser.add_argument("-o", "--output", default="fft-history.html")
    parser.add_argument("--who", nargs="+",
                        default=["Ramza", "Orlandu", "Rafa", "Agrias"])
    args = parser.parse_args()

    points = collect(args.path)
    caps = stats.load()["functional_raw_caps"]
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(build(points, args.who, caps))
    print(f"{len(points)} уникальных точек по времени -> {args.output}")


if __name__ == "__main__":
    main()
