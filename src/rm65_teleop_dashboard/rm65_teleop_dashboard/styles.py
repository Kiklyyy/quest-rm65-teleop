"""One restrained, offline Qt theme shared by every dashboard widget."""

BACKGROUND = "#080f1b"
PANEL = "#0d1827"
CARD = "#102030"
LINE = "#20374b"
TEXT = "#e5eff9"
SECONDARY = "#8297ac"
COLORS = {
    "green": "#36d5a4",
    "blue": "#4ea6ee",
    "orange": "#e8b367",
    "red": "#f27983",
    "grey": "#8191a3",
}


def stylesheet(compact=False):
    """Scale typography at laptop widths without absolute widget placement."""
    size = 11 if compact else 12
    title = 22 if compact else 27
    value = 17 if compact else 20
    section = 11 if compact else 13
    return """
    QWidget {
        color: %(text)s; font-family: "Noto Sans CJK SC", "Microsoft YaHei", "DejaVu Sans", sans-serif;
        font-size: %(size)dpx;
    }
    QMainWindow, QWidget#DashboardRoot { background: %(bg)s; }
    QFrame[role="panel"] { background: %(panel)s; border: 1px solid %(line)s; border-radius: 10px; }
    QFrame[role="card"] { background: %(card)s; border: 1px solid %(line)s; border-radius: 8px; }
    QFrame[role="inset"] { background: #0b1725; border: 1px solid #1a3043; border-radius: 7px; }
    QLabel { background: transparent; border: none; }
    QLabel[role="title"] { font-size: %(title)dpx; font-weight: 600; letter-spacing: 1px; }
    QLabel[role="section"] { font-size: %(section)dpx; font-weight: 600; color: #d7e7f6; }
    QLabel[role="eyebrow"] { font-size: 10px; font-weight: 600; color: #89a8c3; letter-spacing: 1px; }
    QLabel[role="secondary"] { color: %(muted)s; font-size: 11px; }
    QLabel[role="value"] { font-size: %(value)dpx; font-weight: 600; }
    QLabel[role="numeric"] { font-family: "DejaVu Sans Mono", "Consolas", monospace; }
    QLabel[role="pill"] { border-radius: 5px; padding: 4px 8px; font-size: 11px; font-weight: 600; }
    QLabel[tone="green"] { color: #36d5a4; }
    QLabel[tone="blue"] { color: #4ea6ee; }
    QLabel[tone="orange"] { color: #e8b367; }
    QLabel[tone="red"] { color: #f27983; }
    QLabel[tone="grey"] { color: #8191a3; }
    QLabel[role="pill"][tone="green"] { background: #11382f; border: 1px solid #24634f; }
    QLabel[role="pill"][tone="blue"] { background: #132d48; border: 1px solid #244d73; }
    QLabel[role="pill"][tone="orange"] { background: #3a2b1b; border: 1px solid #60482c; }
    QLabel[role="pill"][tone="red"] { background: #3d202b; border: 1px solid #653543; }
    QLabel[role="pill"][tone="grey"] { background: #1c2835; border: 1px solid #324252; }
    QProgressBar { border: none; background: #1b3042; border-radius: 3px; height: 5px; color: transparent; }
    QProgressBar::chunk { background: #4ea6ee; border-radius: 3px; }
    QProgressBar[tone="green"]::chunk { background: #36d5a4; }
    QProgressBar[tone="orange"]::chunk { background: #e8b367; }
    QProgressBar[tone="grey"]::chunk { background: #667b90; }
    QComboBox { background: #122334; border: 1px solid #294258; border-radius: 5px; padding: 4px 12px; min-width: 90px; }
    QComboBox::drop-down { border: none; width: 16px; }
    QComboBox QAbstractItemView { background: #122334; border: 1px solid #294258; selection-background-color: #244a68; }
    QTableWidget { background: #0d1827; border: none; gridline-color: #172c3e; selection-background-color: #18354f; }
    QHeaderView::section { background: #122334; color: #91adc6; border: none; border-bottom: 1px solid #294258; padding: 5px; font-size: 10px; }
    QTableWidget::item { padding-left: 7px; border-bottom: 1px solid #16293a; }
    QScrollArea { background: transparent; border: none; }
    QScrollArea > QWidget > QWidget { background: transparent; }
    QScrollBar:vertical { width: 5px; background: #0c1623; margin: 0px; }
    QScrollBar::handle:vertical { background: #2b465e; min-height: 24px; border-radius: 2px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar:horizontal { height: 5px; background: #0c1623; }
    QScrollBar::handle:horizontal { background: #2b465e; min-width: 24px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
    QSplitter::handle { background: transparent; width: 7px; height: 7px; }
    QToolTip { color: #e5eff9; background: #142b3d; border: 1px solid #345670; padding: 5px; }
    """ % dict(text=TEXT, size=size, title=title, value=value, section=section, bg=BACKGROUND,
               panel=PANEL, card=CARD, line=LINE, muted=SECONDARY)


def apply_tone(widget, tone):
    """Change a QSS state property only when necessary (no per-widget QSS)."""
    if widget.property("tone") == tone:
        return
    widget.setProperty("tone", tone)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
