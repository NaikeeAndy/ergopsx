"""Сборка самостоятельного приложения для Windows, Linux и macOS.

Кладёт внутрь интерпретатор, Qt и движок из `tools/` - пользователю
ничего доустанавливать не нужно.

    qt/.venv/bin/python qt/build.py
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAME = "NaikeeSaveManager"


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("нет PyInstaller, ставлю…")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                        "pyinstaller"], check=True)

    # Движок и его таблицы кладём внутрь: без них не читаются названия
    # игр, шаблоны полей и карта комнат Vagrant Story.
    sep = ";" if os.name == "nt" else ":"
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", NAME, "--windowed",
        "--add-data", f"{os.path.join(ROOT, 'tools')}{sep}tools",
        # Модули движка ищут таблицы рядом с собой, а упаковщик
        # складывает их плоско - кладём папку и туда.
        "--add-data", f"{os.path.join(ROOT, 'tools', 'data')}{sep}data",
        "--paths", os.path.join(ROOT, "tools"),
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build"),
        # Разборщики подключаются по имени, статический анализ их не видит.
        *sum((["--hidden-import", name] for name in HIDDEN), []),
        os.path.join(HERE, "app.py"),
    ]
    icon = os.path.join(ROOT, "swift", "icon", "MemCardSaver.icns")
    if sys.platform == "darwin" and os.path.exists(icon):
        args[args.index("--windowed") + 1:args.index("--windowed") + 1] = [
            "--icon", icon]
    subprocess.run(args, check=True, cwd=HERE)
    print("готово:", os.path.join(HERE, "dist"))


HIDDEN = [
    "psxapp", "psxbuild", "psxchoco", "psxchronicles", "psxconvert",
    "psxcrash2", "psxff5", "psxff5data", "psxff6", "psxff6data", "psxff7",
    "psxff7data", "psxff8", "psxff8data", "psxff8read", "psxff9", "psxff9data",
    "psxfft", "psxfftdata", "psxfftstats", "psxid", "psxpe2", "psxplaytime",
    "psxpocket", "psxre1", "psxre1data", "psxsign", "psxsotn", "psxsotndata",
    "psxstate", "psxtemplate", "psxvagrant",
]

if __name__ == "__main__":
    sys.exit(main())
