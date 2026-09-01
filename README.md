# ErgoPSX Save Manager

Reads and inspects PlayStation 1 saves: memory cards, single saves, every
container format in common use, detailed breakdowns for twelve games, and
working with saves directly on a PS3 or a Nintendo Switch over FTP.

The app **never overwrites anything**. Changing a region, building a card,
converting, uploading to a console — always into a new file.

## What it does

**Card and save formats.** Raw image (`.mcr`, `.mcd`, `.VM1`), DexDrive
`.gme`, VGS, PSP `.vmp`, Memory Juggler `.psx`, PS3 `.psv`, `.mcs`, MCX.
Conversion between them, region switching, splitting a card into single
saves and building a card back.

**Signing.** AES-128 and HMAC-SHA1 for `.psv` and `.vmp` — consoles accept
the files it builds instead of rejecting them.

**Icons.** 16×16 BGR555 decoding, every animation frame, transparency from
the STP bit.

**Detailed game breakdowns.** Final Fantasy V, VI, VII, VIII, IX, Tactics,
Castlevania: Symphony of the Night, Castlevania Chronicles, Resident Evil,
Vagrant Story, Parasite Eve II, Crash Bandicoot 2. Party, inventory,
equipment, magic, playtime, progress. Plus template-driven field reading
for a number of other games.

**Consoles over FTP.** Browsing files on a PS3 and a Switch, looking inside
memory cards without downloading them, uploading game images, building a
card out of saves gathered from several places.

**Seven languages.** English, Russian, French, German, Japanese, Chinese,
Polish; switched on the fly from the settings. English is the source
language: it is written in the code itself and serves as the lookup key,
while the others live in tables under `tools/data/i18n`. Both versions
share the same tables.

**Two engines, checked against each other.** One in Swift, one in Python;
`python3 tools/psxverify.py saves` runs both over a collection and compares
them field by field. There should be no divergence — this is what catches
mistakes that look plausible to the eye.

## Getting it

There are no prebuilt downloads yet — build it from source. Start by
cloning the repository:

```sh
git clone https://github.com/NaikeeAndy/ergopsx.git
cd ergopsx
```

### Linux

Python 3.12 or newer. Qt also needs a handful of system libraries; without
them PySide6 fails with `could not load the Qt platform plugin "xcb"`.

Debian and Ubuntu:

```sh
sudo apt-get install python3-venv libegl1 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
  libxcb-render-util0 libxcb-shape0 libxcb-cursor0
```

That list is what CI installs on Ubuntu, so it is known to be enough. On
other distributions the same libraries carry different names — look for
EGL, xkbcommon-x11 and the xcb-util family.

Then:

```sh
python3 -m venv qt/.venv
qt/.venv/bin/python -m pip install PySide6
qt/.venv/bin/python qt/app.py
```

To get a standalone application that runs without Python installed:

```sh
qt/.venv/bin/python -m pip install pyinstaller
qt/.venv/bin/python qt/build.py      # lands in qt/dist
```

### Windows

Python 3.12 or newer, nothing else to install:

```sh
python -m venv qt\.venv
qt\.venv\Scripts\python -m pip install PySide6
qt\.venv\Scripts\python qt\app.py
```

The standalone build works the same way as on Linux, through
`qt/build.py`.

### macOS

A native Swift app; Xcode 15 or newer, macOS 14 or newer:

```sh
./swift/build-app.sh
open swift/ErgoPSXSaveManager.app
./swift/build-dmg.sh          # disk image for distribution
```

The Qt version runs on macOS as well, and is the one to use for
development on Linux and Windows.

### Which of the two to build

Both read the same saves and share the same engine and string tables. The
Swift app is for macOS only. The Qt app runs everywhere, including macOS.

GitHub Actions builds all three systems on a version tag, so tagged
releases carry ready-made binaries.

Command-line tools (Python 3, no dependencies):

```sh
python3 tools/psxid.py <file>          # identify a save
python3 tools/psxgallery.py <folder>   # HTML gallery
python3 tools/psxconvert.py --help     # conversion
python3 tools/psxbuild.py --help       # card building
```

## The game title database

Game names are looked up by serial in an external database — 10,937
entries, `TitlesDB_PS1_English.txt` from
[sd2psx-save-converter](https://github.com/Kyuu-Ji/sd2psx-save-converter),
which in turn takes it from
[Title-Database-Scrapper](https://github.com/GDX-X/Title-Database-Scrapper).
It is not included here: no licence is stated for it, and we are not going
to redistribute it. Everything works without it, but instead of names the
app shows "Unknown game" and fills the list on the left with save
signatures.

Put the file at
`reference/psxsaves/sd2psx-save-converter/BAT/TitlesDB_PS1_English.txt`
and run:

```sh
python3 tools/psxexport.py
```

It lays the database and the string tables out for both builds.

## Console profiles

Copy `tools/data/consoles.example.json` to `tools/data/consoles.json` and
fill in your own addresses. That file is not in the repository and must
never end up in it — it holds a password.

## Credits

PS1 save formats were worked out by dozens of people, over years and mostly
for free. This project would not exist without them; almost nothing here
was derived from scratch.

### Game format research

| Project | What it gave | Licence |
|---|---|---|
| [ser-pounce/rood-reverse](https://github.com/ser-pounce/rood-reverse) | Vagrant Story: save decryption, `savedata_t` layout, character table, room map | CC0 |
| [myst6re/hyne](https://github.com/myst6re/hyne) | Final Fantasy VIII: save layout and checksum table | GPL-3.0 |
| [sithlord48/ff7tk](https://github.com/sithlord48/ff7tk) | Final Fantasy VII: save structures with offsets spelled out | LGPL-3.0 |
| [everything8215/ff5](https://github.com/everything8215/ff5) | Final Fantasy V: disassembly, RAM map, character table | — |
| [GabeRealB/parasite-eve-2-decomp](https://github.com/GabeRealB/parasite-eve-2-decomp) | Parasite Eve II: save record size and layout | CC0 |
| [giuse94/PSDX](https://github.com/giuse94/PSDX) | Crash Bandicoot 2: offsets and checksum | Unlicense |
| game-tools-collection | Field templates for FFT, SotN, Resident Evil and others | — |

### Containers, signing, cards

| Project | What it gave |
|---|---|
| [MemcardRex](https://github.com/ShendoXT/memcardrex) | Container formats and PSV signing |
| [save-file-converter](https://github.com/euanjt/save-file-converter) | Conversion and signing |
| psv-save-converter | PSV header and signature |
| ps1vmc-tool, ps3mca-ps1 | Working with PS3 cards |
| [PSDevWiki](https://www.psdevwiki.com/) | `.VM1`, `.PSV`, `.VMP` documentation |

### Names and tables

| Source | What it gave |
|---|---|
| [Title-Database-Scrapper](https://github.com/GDX-X/Title-Database-Scrapper) | Game titles by serial |
| RPGe (Final Fantasy V translation) | Job, item and spell names |
| ff5-names | Modern FF5 item naming |
| forums.qhimm.com | Final Fantasy VIII save research |
| [wiki.ffrtt.ru](https://wiki.ffrtt.ru/) and Data Crystal | Final Fantasy VII save map |

### Consoles

| Project | What it gave |
|---|---|
| [ITotalJustice/ftpsrv](https://github.com/ITotalJustice/ftpsrv) | FTP server for the Switch, including as a system module |
| webMAN MOD, multiMAN | FTP on the PS3 |
| [DuckStation](https://github.com/stenzek/duckstation) | Memory card naming we checked ourselves against |

### What exactly was taken

The distinction matters. **Findings** — offsets, field order, time units,
checksum algorithms — are facts about the games, established by other
people's work. They are everywhere in this project and cannot be removed:
the parsing rests on them. The one thing that can be done with them is to
name who established them, which is what the tables above do. If the
attribution is wrong or incomplete, write and it will be fixed.

**Copied verbatim** are only tables, and here is the list of them — with
those the conversation is concrete:

| File | From | Can it be replaced |
|---|---|---|
| `psxff8.json`, the `CRC_TABLE` field | hyne, GPL-3.0 | yes — the table is generated from polynomial `0x1021`, with one correction: entry 255 is zero, otherwise the checksums do not match |
| `VagrantText.swift`, character table | rood-reverse, CC0 | the licence allows it |
| `templates.json` | game-tools-collection | no licence stated — needs checking |
| FF5 item and job names | the RPGe patch | a fan translation, terms of distribution not spelled out |

The FF8 CRC table need not be stored at all — code can generate it. The
rest can be rebuilt from scratch if it comes to that.

If your project is used here and is missing from the list, write and it
will be added. If you object to how **your table** is used, write as well:
it really can be removed or rebuilt.

## Contact

Open for suggestions and collaboration — **dktgsitu@gmail.com**. Bug
reports, missing games, wrong offsets, attribution that needs fixing: all
welcome, by mail or as an issue.

## Licence

MIT — see `LICENSE`. The licence covers the code of this project. Data and
research taken from the sources listed above remain under their own
licences.
