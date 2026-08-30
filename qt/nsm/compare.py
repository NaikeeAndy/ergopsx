"""Сравнение двух сейвов: что различается, а что совпало.

Списки сличаются **по названию, а не по позиции**: один добавленный
предмет сдвигает весь инвентарь и даёт сотни ложных различий. Но имена
бывают неуникальны - в отряде после гринда сразу по нескольку одинаковых,
поэтому одноимённых нумеруем.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QGridLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from . import digest, lang
from .style import sheet
from . import lang
from .theme import Palette


def _flatten(made, prefix=""):
    """Разбор - в плоские пары «путь, значение»."""
    out = {}
    if made is None:
        return out
    for field in made.fields:
        out[field.label] = field.value
    seen = {}
    for unit in made.members:
        name = unit.name or unit.role
        seen[name] = seen.get(name, 0) + 1
        # Одноимённых нумеруем: иначе различия последнего затирают
        # предыдущих, и дифф выглядит короче, чем есть.
        key = name if seen[name] == 1 else f"{name} #{seen[name]}"
        out[lang.t(f"{key} · уровень", f"{key} · level")] = unit.level
        for stat in unit.stats:
            out[f"{key} · {stat.label}"] = stat.value
        if unit.gear:
            out[lang.t(f"{key} · экипировка", f"{key} · equipment")] = ", ".join(unit.gear)
        if unit.extra:
            out[lang.t(f"{key} · прочее", f"{key} · other")] = unit.extra
    for part in made.sections:
        for field in part.items:
            out[f"{part.title} · {field.label}"] = field.value or lang.t("есть", "present")
    return out


class CompareView(QDialog):
    def __init__(self, left_item, right_item, library, palette: Palette,
                 parent=None):
        super().__init__(parent)
        self.p = palette
        self.setWindowTitle(lang.t("Сравнение", "Comparison"))
        self.resize(900, 640)
        # Без имени правило фона не срабатывает, и окно
        # остаётся белым - текст на нём почти не виден.
        self.setObjectName("root")
        self.setStyleSheet(sheet(palette))

        left = _flatten(digest.build(library.detail(left_item)))
        right = _flatten(digest.build(library.detail(right_item)))
        keys = sorted(set(left) | set(right))
        rows = [(key, left.get(key, "—"), right.get(key, "—"))
                for key in keys if left.get(key) != right.get(key)]

        column = QVBoxLayout(self)
        column.setContentsMargins(18, 16, 18, 16)
        column.setSpacing(10)

        head = QLabel(f"{left_item.title}   ·   {right_item.title}")
        font = head.font()
        font.setPointSizeF(14)
        font.setBold(True)
        head.setFont(font)
        column.addWidget(head)

        note = QLabel(
            lang.t(f"{len(rows)} различий · совпало {len(keys) - len(rows)}",
                   f"{len(rows)} differences · {len(keys) - len(rows)} match"))
        note.setObjectName("dim")
        column.addWidget(note)

        if not rows:
            done = QLabel(lang.t(
                lang.t("Различий нет — сейвы совпадают по всем полям, ", "No differences — the saves match on every field ")
                + lang.t("которые мы читаем", "we read"),
                "No differences — the saves match on every field we read"))
            done.setObjectName("faint")
            column.addWidget(done)
            column.addStretch(1)
            return

        area = QScrollArea()
        area.setWidgetResizable(True)
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)
        for index, title in enumerate((lang.t("Поле", "Field"),
                                       lang.t("СЛЕВА", "LEFT"),
                                       lang.t("СПРАВА", "RIGHT"))):
            label = QLabel(title)
            label.setObjectName("head")
            grid.addWidget(label, 0, index)
        for row, (key, was, now) in enumerate(rows, start=1):
            grid.addWidget(QLabel(key), row, 0)
            for column_index, value in ((1, was), (2, now)):
                cell = QLabel(str(value))
                cell.setObjectName("dim" if value == "—" else None)
                grid.addWidget(cell, row, column_index)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        area.setWidget(body)
        column.addWidget(area, 1)
