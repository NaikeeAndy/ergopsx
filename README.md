# Naikee's Save Manager

Чтение и разбор сохранений PlayStation 1: карты памяти, отдельные сейвы,
контейнеры всех ходовых форматов, подробный разбор двенадцати игр и работа
с сохранениями прямо на PS3 и Nintendo Switch по FTP.

Приложение **ничего не перезаписывает**. Смена региона, сборка карты,
конвертация, отправка на консоль — всегда в новый файл.

## Что умеет

**Форматы карт и сейвов.** Сырой образ (`.mcr`, `.mcd`, `.VM1`), DexDrive
`.gme`, VGS, PSP `.vmp`, Memory Juggler `.psx`, PS3 `.psv`, `.mcs`, MCX.
Конвертация между ними, смена региона, разбор карты на отдельные сейвы и
сборка карты обратно.

**Подпись.** AES-128 и HMAC-SHA1 для `.psv` и `.vmp` — консоль принимает
собранные файлы, а не отвергает их.

**Иконки.** Декодирование 16×16 BGR555, все кадры анимации, прозрачность
по STP-биту.

**Подробный разбор игр.** Final Fantasy V, VI, VII, VIII, IX, Tactics,
Castlevania: Symphony of the Night, Castlevania Chronicles, Resident Evil,
Vagrant Story, Parasite Eve II, Crash Bandicoot 2. Отряд, инвентарь,
экипировка, магия, наигранное время, прогресс. Плюс общий разбор по
шаблонам ещё для нескольких игр.

**Консоли по FTP.** Обход файлов на PS3 и Switch, просмотр содержимого карт
без скачивания, загрузка образов игр, сборка карты из сейвов разных мест.

## Как запустить

Приложение для macOS:

```sh
./swift/build-app.sh
open swift/NaikeeSaveManager.app
```

Инструменты командной строки (Python 3, зависимостей нет):

```sh
python3 tools/psxid.py <файл>          # опознать сейв
python3 tools/psxgallery.py <папка>    # HTML-галерея
python3 tools/psxconvert.py --help     # конвертация
python3 tools/psxbuild.py --help       # сборка карты
```

## База названий игр

В репозиторий не входит: это чужая база, у неё своя лицензия. Возьмите её
из [Title-Database-Scrapper](https://github.com/GDX-X/Title-Database-Scrapper)
и положите рядом, затем выполните `python3 tools/psxexport.py`. Без неё всё
работает, но игры показываются серийниками вместо названий.

## Профили консолей

Скопируйте `tools/data/consoles.example.json` в `tools/data/consoles.json`
и впишите свои адреса. Файл в репозиторий не входит и не должен в него
попадать — в нём пароль.

## Благодарности

Форматы сохранений PS1 разбирали десятки людей, годами и по большей части
безвозмездно. Без их работы этот проект был бы невозможен — здесь почти
ничего не выведено с нуля.

### Разборы форматов игр

| Проект | Что дал | Лицензия |
|---|---|---|
| [ser-pounce/rood-reverse](https://github.com/ser-pounce/rood-reverse) | Vagrant Story: расшифровка сейва, раскладка `savedata_t`, таблица символов, карта комнат | CC0 |
| [myst6re/hyne](https://github.com/myst6re/hyne) | Final Fantasy VIII: раскладка сейва и таблица контрольной суммы | GPL-3.0 |
| [sithlord48/ff7tk](https://github.com/sithlord48/ff7tk) | Final Fantasy VII: структуры сейва с проставленными смещениями | LGPL-3.0 |
| [everything8215/ff5](https://github.com/everything8215/ff5) | Final Fantasy V: дизассемблировка, карта RAM, таблица символов | — |
| [GabeRealB/parasite-eve-2-decomp](https://github.com/GabeRealB/parasite-eve-2-decomp) | Parasite Eve II: размер и раскладка записи сейва | CC0 |
| [giuse94/PSDX](https://github.com/giuse94/PSDX) | Crash Bandicoot 2: смещения и контрольная сумма | Unlicense |
| game-tools-collection | Шаблоны полей для FFT, SotN, Resident Evil и других | — |

### Контейнеры, подпись, работа с картами

| Проект | Что дал |
|---|---|
| [MemcardRex](https://github.com/ShendoXT/memcardrex) | Форматы контейнеров и подпись PSV |
| [save-file-converter](https://github.com/euanjt/save-file-converter) | Конвертация и подпись |
| psv-save-converter | Заголовок и подпись PSV |
| ps1vmc-tool, ps3mca-ps1 | Работа с картами PS3 |
| [PSDevWiki](https://www.psdevwiki.com/) | Описание `.VM1`, `.PSV`, `.VMP` |

### Названия и таблицы

| Источник | Что дал |
|---|---|
| [Title-Database-Scrapper](https://github.com/GDX-X/Title-Database-Scrapper) | База названий игр по серийникам |
| RPGe (перевод Final Fantasy V) | Названия работ, предметов и заклинаний |
| ff5-names | Современный нейминг предметов FF5 |
| forums.qhimm.com | Разбор сейвов Final Fantasy VIII |
| [wiki.ffrtt.ru](https://wiki.ffrtt.ru/) и Data Crystal | Карта сейва Final Fantasy VII |

### Консоли

| Проект | Что дал |
|---|---|
| [ITotalJustice/ftpsrv](https://github.com/ITotalJustice/ftpsrv) | FTP-сервер для Switch, в том числе системным модулем |
| webMAN MOD, multiMAN | FTP на PS3 |
| [DuckStation](https://github.com/stenzek/duckstation) | Именование карт памяти, с которым мы сверялись |

Если ваш проект здесь использован, а в списке его нет — напишите,
добавлю. Если использование чего-то из перечисленного вас не устраивает —
тоже напишите, уберу.

## Лицензия

MIT — см. `LICENSE`. Лицензия распространяется на код этого проекта.
Данные и разборы, взятые из перечисленных выше источников, остаются под
своими лицензиями.
