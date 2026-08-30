"""Таблица стилей: те же цвета и та же плотность, что в версии для macOS."""

from .theme import Palette, gradient


def sheet(p: Palette) -> str:
    return f"""
    QWidget {{
        background: transparent;
        color: {p.ink};
        font-size: 13px;
    }}
    QWidget#root, QDialog#root {{ background: {gradient(p.background)}; }}
    QWidget#bar {{
        background: {gradient(p.bar)};
        border-bottom: 1px solid {p.bar_line};
    }}
    QWidget#panel {{ background: {p.panel}; }}
    QFrame#divider {{ background: {p.panel_line}; max-width: 1px; border: none; }}
    QFrame#hdivider {{ background: {p.panel_line}; max-height: 1px; border: none; }}

    QLabel#dim {{ color: {p.ink_soft}; }}
    QLabel#faint {{ color: {p.ink_faint}; }}
    QLabel#accent {{ color: {p.accent}; }}
    QLabel#head {{ color: {p.ink_faint}; font-size: 11px; letter-spacing: 1px; }}

    QLineEdit {{
        background: {p.well};
        border: 1px solid {p.control_edge};
        border-radius: 7px;
        padding: 6px 10px;
        selection-background-color: {p.accent};
        selection-color: {p.accent_ink};
    }}

    QPushButton {{
        background: {p.control};
        border: 1px solid {p.control_edge};
        border-radius: 7px;
        padding: 6px 13px;
    }}
    QPushButton:hover {{ border-color: {p.accent}; }}
    QPushButton:disabled {{ color: {p.ink_faint}; border-color: {p.panel_line}; }}
    QPushButton#primary {{
        background: {p.accent};
        color: {p.accent_ink};
        border: none;
        font-weight: 600;
    }}

    QComboBox {{
        background: {p.control};
        border: 1px solid {p.control_edge};
        border-radius: 7px;
        padding: 5px 10px;
    }}
    QComboBox QAbstractItemView {{
        background: {p.panel};
        border: 1px solid {p.panel_line};
        selection-background-color: {p.accent};
        selection-color: {p.accent_ink};
    }}

    QListWidget {{ background: transparent; border: none; outline: none; }}
    QListWidget::item {{ border-radius: 8px; }}
    QListWidget::item:selected {{ background: transparent; }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.panel_line}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QMenuBar {{ background: {gradient(p.bar)}; }}
    QMenuBar::item:selected {{ background: {p.accent}; color: {p.accent_ink}; }}
    QMenu {{ background: {p.panel}; border: 1px solid {p.panel_line}; }}
    QMenu::item:selected {{ background: {p.accent}; color: {p.accent_ink}; }}

    QToolTip {{
        background: {p.panel};
        color: {p.ink};
        border: 1px solid {p.panel_line};
        padding: 4px;
    }}
    """
