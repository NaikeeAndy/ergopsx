#!/usr/bin/env python3
"""Работа с сейвами на консоли по FTP.

PS3 с кастомной прошивкой поднимает FTP через webMAN MOD или multiMAN, сейвы
лежат в /dev_hdd0/home/<профиль>/savedata/. Switch с Atmosphere - через
sys-ftpd, карты памяти эмуляторов PS1 лежат обычными файлами на SD.

Зависимостей нет: ftplib из стандартной библиотеки.
"""

import ftplib
import json
import re
import time
import os
import posixpath
import stat

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "data", "consoles.json")

# Куда обычно смотреть на каждой из консолей - подставляется в новый профиль.
DEFAULTS = {
    "ps3": {"port": 21, "path": "/dev_hdd0/home", "user": "anonymous",
            "label": "PS3"},
    "switch": {"port": 5000, "path": "/switch/duckstation/memcards",
               "user": "anonymous", "label": "Switch"},
}

TIMEOUT = 8


def load():
    if not os.path.exists(CONFIG):
        return {}
    with open(CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


def save(profiles):
    """Пишет профили и закрывает файл от чужих: там лежит пароль."""
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump(profiles, fh, ensure_ascii=False, indent=1)
    os.chmod(CONFIG, stat.S_IRUSR | stat.S_IWUSR)


ATTEMPTS = 3


def _out(path):
    """Путь наружу: канал открыт latin-1, отдаём в него байты UTF-8."""
    return path.encode("utf-8").decode("latin-1")


def _in(name):
    """Имя из ответа обратно в текст: сперва UTF-8, иначе оставляем как есть."""
    raw = name.encode("latin-1", "replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def connect(profile, attempts=ATTEMPTS):
    """Подключение с повторами.

    Встроенный сервер sphaira отвечает не с первого раза: порт занят всегда,
    а обслуживать соединения он готов не сразу. Один отказ ещё ничего не
    значит, поэтому пробуем несколько раз, прежде чем сдаться."""
    last = None
    for attempt in range(attempts):
        ftp = ftplib.FTP(timeout=TIMEOUT)
        # webMAN MOD пишет в ответ температуру консоли со знаком градуса, а
        # ftplib по умолчанию ждёт UTF-8 и падает на этом байте. latin-1
        # переносит любые байты без потерь, имена перекодируем сами.
        ftp.encoding = "latin-1"
        try:
            ftp.connect(profile["host"], int(profile.get("port") or 21))
            ftp.login(profile.get("user") or "anonymous",
                      profile.get("password") or "")
            try:
                ftp.set_pasv(True)
            except Exception:
                pass
            return ftp
        except Exception as error:
            last = error
            try:
                ftp.close()
            except Exception:
                pass
            if attempt + 1 < attempts:
                time.sleep(1.5)
    raise last


def _parse_list(line):
    """Строка LIST в стиле Unix -> (имя, размер, папка ли)."""
    parts = line.split(maxsplit=8)
    if len(parts) < 9:
        return None
    size = int(parts[4]) if parts[4].isdigit() else 0
    return _in(parts[8]), size, line[0] == "d"


def listdir(ftp, path):
    """[(имя, размер, папка ли)] - через MLSD, LIST или NLST, что ответит."""
    path = path or "/"
    try:
        return [(_in(name), int(facts.get("size", 0)),
                 facts.get("type") == "dir")
                for name, facts in ftp.mlsd(_out(path))
                if name not in (".", "..")]
    except Exception:
        pass
    lines = []
    try:
        ftp.retrlines(f"LIST {_out(path)}", lines.append)
        out = [_parse_list(line) for line in lines]
        out = [entry for entry in out if entry and entry[0] not in (".", "..")]
        if out:
            return out
    except Exception:
        pass
    # Совсем скупой сервер: только имена, тип определяем попыткой войти.
    names = [_in(posixpath.basename(n)) for n in ftp.nlst(_out(path))]
    out = []
    for name in names:
        if name in (".", ".."):
            continue
        target = posixpath.join(path, name)
        try:
            ftp.cwd(_out(target))
            out.append((name, 0, True))
        except Exception:
            out.append((name, 0, False))
    return out


def download(ftp, remote):
    chunks = []
    ftp.retrbinary(f"RETR {_out(remote)}", chunks.append)
    return b"".join(chunks)


def exists(ftp, remote):
    """Есть ли такой файл на консоли и какого он размера."""
    try:
        return ftp.size(_out(remote))
    except Exception:
        pass
    try:
        folder = posixpath.dirname(remote) or "/"
        name = posixpath.basename(remote)
        return next((size for n, size, is_dir in listdir(ftp, folder)
                     if n == name and not is_dir), None)
    except Exception:
        return None


def upload(ftp, remote, data):
    import io
    ftp.storbinary(f"STOR {_out(remote)}", io.BytesIO(data))
    return len(data)


def walk_saves(ftp, root, suffixes=(".psv", ".mcs", ".mcr", ".srm", ".vmp",
                                    ".gme", ".mcd", ".vm1"), depth=3):
    """Обходит папки консоли и собирает всё похожее на сейвы."""
    found = []
    stack = [(root, 0)]
    while stack:
        path, level = stack.pop()
        try:
            entries = listdir(ftp, path)
        except Exception:
            continue
        for name, size, is_dir in entries:
            full = posixpath.join(path, name)
            if is_dir:
                if level < depth:
                    stack.append((full, level + 1))
            elif os.path.splitext(name)[1].lower() in suffixes:
                found.append((full, size))
    return found


# --- проверка соединения ----------------------------------------------------

# Куда смотреть при проверке. У Switch родных сейвов на SD нет - там лежат
# только карты памяти эмуляторов PS1, и почти всегда это RetroArch.
CHECK_PATHS = {
    "ps3": ("/dev_hdd0/home", "/dev_hdd0/savedata", "/dev_hdd0", "/"),
    # DuckStation держит карты у себя, а не в папке RetroArch. Проверено на
    # живой консоли: /switch/duckstation/memcards, файлы <имя рома>_1.mcd.
    # У RetroArch путь берётся из retroarch.cfg (savefile_directory) и при
    # sort_savefiles_enable=true раскладывается по подпапкам с именем ядра.
    "switch": ("/switch/duckstation/memcards", "/switch/duckstation",
               "/retroarch/cores/savefiles", "/switch", "/"),
}

# Отсюда начинается поиск сейвов, если в профиле не указано иное.
SCAN_ROOTS = {
    "ps3": ("/dev_hdd0/home", "/dev_hdd0/savedata"),
    "switch": ("/switch/duckstation/memcards", "/retroarch/cores/savefiles"),
}


def check(host, port=21, user="anonymous", password="", paths=()):
    """Пошагово проверяет соединение и возвращает отчёт строками."""
    report = []
    ftp = ftplib.FTP(timeout=TIMEOUT)
    ftp.encoding = "latin-1"
    try:
        ftp.connect(host, int(port))
        report.append(("подключение", "ок", ftp.getwelcome().strip()))
    except Exception as error:
        report.append(("подключение", "не вышло", str(error)))
        return report
    try:
        ftp.login(user or "anonymous", password or "")
        report.append(("вход", "ок", f"логин {user or 'anonymous'}"))
    except Exception as error:
        report.append(("вход", "не вышло", str(error)))
        ftp.close()
        return report
    try:
        report.append(("система", "ок", ftp.sendcmd("SYST")))
    except Exception as error:
        report.append(("система", "не отвечает", str(error)))
    # какой способ листинга понимает эта прошивка
    for name, probe in (("MLSD", lambda: list(ftp.mlsd("/"))),
                        ("LIST", lambda: _lines(ftp, "LIST /")),
                        ("NLST", lambda: ftp.nlst("/"))):
        # каждая проба на своём соединении: упавшая оставляет в канале
        # непрочитанный ответ, и следующая падает уже не по своей вине
        try:
            ftp.voidcmd("NOOP")
        except Exception:
            pass
        try:
            got = probe()
            report.append((f"листинг {name}", "ок", f"{len(got)} записей"))
            break
        except Exception as error:
            report.append((f"листинг {name}", "не поддержан", str(error)[:60]))
    for path in paths or ("/",):
        try:
            entries = listdir(ftp, path)
            names = ", ".join(n for n, _, _ in entries[:6])
            report.append((f"папка {path}", "ок",
                           f"{len(entries)} записей: {names}"))
        except Exception as error:
            report.append((f"папка {path}", "не открылась", str(error)[:60]))
    ftp.close()
    return report


def _lines(ftp, command):
    out = []
    ftp.retrlines(command, out.append)
    return out


def find(port, network=None, timeout=1.0):
    """Ищет в локальной сети адреса с открытым портом."""
    import socket as _socket
    if network is None:
        probe = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        network = ".".join(probe.getsockname()[0].split(".")[:3])
        probe.close()
    found = []
    import concurrent.futures
    def probe_one(n):
        """Открытого порта мало: в сети с VPN соединение принимают все адреса.
        Считаем находкой только тех, кто ответил приветствием FTP (код 220)."""
        host = f"{network}.{n}"
        sock = _socket.socket()
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            greeting = sock.recv(64)
            return host if greeting[:3] == b"220" else None
        except Exception:
            return None
        finally:
            sock.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        for result in pool.map(probe_one, range(1, 255)):
            if result:
                found.append(result)
    return network, found


def webman(host, port=80, timeout=6):
    """Читает главную страницу webMAN и собирает команды, которые она сама
    предлагает.

    Только чтение одной страницы. Наугад по адресам вида /xxx.ps3 не ходим:
    рядом с полезными командами у webMAN лежат restart и shutdown, и вызвать
    их случайно нельзя."""
    import html.parser
    import urllib.request

    class Links(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.found = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            for key in ("href", "action", "onclick"):
                value = attrs.get(key) or ""
                for piece in re.findall(r"[/\w.?=&%-]+\.ps3[\w?=&%/-]*", value):
                    if piece not in self.found:
                        self.found.append(piece)

    url = f"http://{host}:{port}/"
    request = urllib.request.Request(url, headers={"User-Agent": "psxapp"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace")
    parser = Links()
    parser.feed(body)
    title = re.search(r"<title>(.*?)</title>", body, re.S | re.I)
    return {"url": url, "title": (title.group(1).strip() if title else ""),
            "commands": parser.found, "size": len(body)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Проверка FTP на консоли")
    sub = parser.add_subparsers(dest="command", required=True)

    test = sub.add_parser("check", help="проверить соединение")
    test.add_argument("host")
    test.add_argument("--port", type=int, default=21)
    test.add_argument("--user", default="anonymous")
    test.add_argument("--password", default="")
    test.add_argument("--kind", choices=("ps3", "switch"), default="ps3")

    web = sub.add_parser("webman", help="что предлагает webMAN на консоли")
    web.add_argument("host")
    web.add_argument("--port", type=int, default=80)

    scan = sub.add_parser("find", help="найти консоль в локальной сети")
    scan.add_argument("--port", type=int, default=21)
    scan.add_argument("--network", help="например 192.168.1")

    args = parser.parse_args()
    if args.command == "check":
        rows = check(args.host, args.port, args.user, args.password,
                     CHECK_PATHS[args.kind])
        width = max(len(step) for step, _, _ in rows)
        for step, status, detail in rows:
            print(f"{step:<{width}}  {status:<14} {detail}")
    elif args.command == "webman":
        info = webman(args.host, args.port)
        print(f"{info['url']}  {info['title']}  ({info['size']} байт)")
        if not info["commands"]:
            print("команд на странице не нашлось")
        for command in info["commands"]:
            print("   ", command)
    else:
        network, found = find(args.port, args.network)
        print(f"сеть {network}.0/24, порт {args.port}")
        print("найдено:", ", ".join(found) if found else "ничего")


if __name__ == "__main__":
    main()
