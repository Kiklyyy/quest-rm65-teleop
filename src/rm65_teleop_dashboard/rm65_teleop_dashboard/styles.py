"""Local system typography and one quiet, light presentation theme."""
import sys

BACKGROUND = '#F5F5F7'
CARD = '#FFFFFF'
SECONDARY = '#6E6E73'
TEXT = '#1D1D1F'
LINE = '#E5E5EA'
COLORS = dict(green='#34C759', blue='#007AFF', orange='#FF9F0A',
              red='#FF3B30', grey='#8E8E93')


def stylesheet(compact=False):
    family = ('Microsoft YaHei UI' if sys.platform == 'win32' else
              '.AppleSystemUIFont' if sys.platform == 'darwin' else 'Noto Sans CJK SC')
    return '''
    QWidget { color: #1D1D1F; background: transparent; font-family: "%s", "DejaVu Sans"; font-size: 13px; }
    QMainWindow, QWidget#DashboardRoot { background: #F5F5F7; }
    QFrame[role="card"] { background: white; border: none; border-radius: 16px; }
    QFrame#Toolbar { background: white; border-bottom: 1px solid #E7E7EB; }
    QFrame#Sidebar { background: #F0F0F3; border-right: 1px solid #E2E2E7; }
    QFrame[role="divider"] { background: #EAEAEF; max-height: 1px; border: none; }
    QLabel { background: transparent; border: none; }
    QLabel[role="pageTitle"] { font-size: %dpx; font-weight: 600; }
    QLabel[role="section"] { font-size: 16px; font-weight: 600; }
    QLabel[role="brand"] { font-size: 18px; font-weight: 600; }
    QLabel[role="toolbarTitle"] { font-size: 17px; font-weight: 600; }
    QLabel[role="secondary"] { color: #6E6E73; font-size: 12px; }
    QLabel[role="caption"] { color: #86868B; font-size: 11px; }
    QLabel[role="value"] { font-size: 24px; font-weight: 500; }
    QLabel[role="metric"] { font-size: 32px; font-weight: 500; }
    QLabel[role="heroState"] { font-size: 24px; font-weight: 500; }
    QLabel[role="demo"] { color: #9B6209; background: #FFF2DB; padding: 4px 8px; border-radius: 6px; font-size: 11px; }
    QLabel[role="alert"] { background: #FFF5E5; color: #965600; padding: 12px 16px; border-radius: 10px; }
    QLabel[role="alert"][tone="red"] { background: #FFF0EE; color: #B52A24; }
    QLabel[tone="orange"] { color: #A36000; }
    QLabel[tone="red"] { color: #C12E26; }
    QLabel[tone="grey"] { color: #86868B; }
    QListWidget#Navigation { background: transparent; border: none; outline: none; padding: 0; }
    QListWidget#Navigation::item { height: 44px; border: none; border-radius: 9px; padding-left: 12px; margin: 2px 0; }
    QListWidget#Navigation::item:hover { background: #E8E8ED; }
    QListWidget#Navigation::item:selected { background: #DDEAFB; color: #0069D9; }
    QToolButton { border: none; background: transparent; padding: 7px 13px; border-radius: 8px; }
    QToolButton:hover { background: #E8E8ED; }
    QFrame[role="segment"] { background: #EAEAEF; border-radius: 10px; }
    QToolButton[role="segment"] { color: #6E6E73; padding: 6px 18px; }
    QToolButton[role="segment"]:checked { background: white; color: #1D1D1F; }
    QToolButton[role="disclosure"] { color: #6E6E73; padding: 5px 0; text-align: left; }
    QProgressBar { border: none; background: #E5E5EA; border-radius: 2px; height: 4px; color: transparent; }
    QProgressBar::chunk { background: #007AFF; border-radius: 2px; }
    QProgressBar[tone="grey"]::chunk { background: #C7C7CC; }
    QTableWidget { background: white; border: none; selection-background-color: #EDF4FE; selection-color: #1D1D1F; outline: none; }
    QHeaderView::section { background: white; color: #6E6E73; font-size: 12px; font-weight: 400; border: none; border-bottom: 1px solid #E5E5EA; padding: 12px 8px; }
    QTableWidget::item { padding: 0 8px; border-bottom: 1px solid #F0F0F3; }
    QScrollArea { background: transparent; border: none; }
    QScrollArea > QWidget > QWidget { background: transparent; }
    QScrollBar:vertical { width: 7px; background: transparent; margin: 2px 0; }
    QScrollBar::handle:vertical { background: #C7C7CC; min-height: 28px; border-radius: 3px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
    QScrollBar:horizontal { height: 7px; background: transparent; }
    QScrollBar::handle:horizontal { background: #C7C7CC; min-width: 28px; border-radius: 3px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    QToolTip { color: #1D1D1F; background: white; border: 1px solid #E5E5EA; padding: 6px; }
    ''' % (family, 26 if compact else 28)


def apply_tone(widget, tone):
    if widget.property('tone') != tone:
        widget.setProperty('tone', tone)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
