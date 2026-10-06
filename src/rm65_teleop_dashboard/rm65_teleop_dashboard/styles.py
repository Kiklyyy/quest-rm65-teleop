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
    QFrame[role="card"], QFrame[role="metricTile"] { background: white; border: 1px solid #E8E8ED; border-radius: 16px; }
    QFrame[role="primaryPanel"] { background: white; border: 1px solid #E8E8ED; border-radius: 18px; }
    QFrame[role="settingsGroup"] { background: white; border: 1px solid #E8E8ED; border-radius: 14px; }
    QFrame#Toolbar { background: white; border-bottom: 1px solid #E7E7EB; }
    QFrame#Sidebar { background: #F2F2F5; border-right: 1px solid #E5E5EA; }
    QFrame[role="divider"] { background: #EAEAEF; max-height: 1px; border: none; }
    QLabel { background: transparent; border: none; }
    QLabel[role="pageTitle"] { font-size: %dpx; font-weight: 600; }
    QLabel[role="section"] { font-size: 18px; font-weight: 600; }
    QLabel[role="cardTitle"] { font-size: 16px; font-weight: 600; }
    QLabel[role="brand"] { font-size: 16px; font-weight: 600; }
    QLabel[role="toolbarTitle"] { font-size: 15px; font-weight: 600; }
    QLabel[role="subtitle"] { color: #6E6E73; font-size: 14px; }
    QLabel[role="secondary"] { color: #6E6E73; font-size: 12px; }
    QLabel[role="caption"] { color: #8E8E93; font-size: 11px; }
    QLabel[role="value"] { font-size: 22px; font-weight: 500; }
    QLabel[role="controllerValue"] { font-size: 18px; font-weight: 500; }
    QLabel[role="jointValue"], QLabel[role="rowTitle"] { font-size: 14px; font-weight: 500; }
    QLabel[role="metric"] { font-size: %dpx; font-weight: 500; }
    QLabel[role="metricUnit"] { font-size: 18px; font-weight: 400; }
    QLabel[role="heroState"] { font-size: 22px; font-weight: 500; }
    QLabel[role="demo"] { color: #9B6209; background: #FFF2DB; padding: 4px 9px; border-radius: 7px; font-size: 11px; }
    QLabel[role="componentIcon"] { background: #F2F5FA; border-radius: 7px; }
    QLabel[role="alert"] { background: #FFF5E5; color: #965600; padding: 12px 16px; border-radius: 10px; }
    QLabel[role="alert"][tone="red"] { background: #FFF0EE; color: #B52A24; }
    QLabel[tone="orange"] { color: #A36000; }
    QLabel[tone="red"] { color: #C12E26; }
    QLabel[tone="green"] { color: #248A3D; }
    QLabel[tone="grey"] { color: #86868B; }
    QListWidget#Navigation { background: transparent; border: none; outline: none; padding: 0; font-size: 14px; }
    QListWidget#Navigation::item { height: 42px; border: none; border-radius: 9px; padding-left: 14px; margin: 2px 0; }
    QListWidget#Navigation::item:hover { background: #E9E9ED; }
    QListWidget#Navigation::item:selected { background: #DCEAFB; color: #007AFF; }
    QToolButton { border: none; background: transparent; padding: 7px 13px; border-radius: 8px; }
    QToolButton:hover { background: #E8E8ED; }
    QFrame[role="segment"] { background: #E9E9ED; border-radius: 9px; }
    QToolButton[role="segment"] { color: #6E6E73; padding: 4px 16px; }
    QToolButton[role="segment"]:checked { background: white; color: #007AFF; }
    QToolButton[role="disclosure"] { color: #6E6E73; padding: 5px 0; text-align: left; }
    QProgressBar { border: none; background: #E5E5EA; border-radius: 2px; height: 5px; color: transparent; }
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
    QDialog { background: #F5F5F7; }
    QPushButton { background: #F2F2F7; color: #1D1D1F; border: 1px solid #E5E5EA; border-radius: 9px; padding: 0 16px; font-size: 14px; font-weight: 500; }
    QPushButton:hover { background: #E9E9ED; }
    QPushButton[compactAction="true"] { font-size: 12px; padding: 0 12px; border-radius: 7px; }
    QPushButton[role="primaryAction"] { background: #007AFF; border: 1px solid #007AFF; color: white; }
    QPushButton[role="primaryAction"]:hover { background: #0071E3; }
    QPushButton[role="primaryAction"]:pressed { background: #0068D1; }
    QPushButton[role="destructiveAction"] { background: #FFF3F2; border: 1px solid #FFD3D0; color: #D70015; }
    QPushButton:disabled { background: #F2F2F7; color: #A3A3AA; border: 1px solid #EBEBF0; }
    QPushButton[role="primaryAction"]:disabled { background: #B7D5FA; color: white; border: 1px solid #B7D5FA; }
    QPushButton[role="destructiveAction"]:disabled { background: #FFF8F7; color: #D7A39F; border: 1px solid #F4DEDC; }
    QPushButton[demoPreview="true"]:disabled { background: #F2F2F7; color: #1D1D1F; border: 1px solid #E5E5EA; }
    QPushButton[role="primaryAction"][demoPreview="true"]:disabled { background: #007AFF; color: white; border: 1px solid #007AFF; }
    QPushButton[role="destructiveAction"][demoPreview="true"]:disabled { background: #FFF3F2; color: #D70015; border: 1px solid #FFD3D0; }
    QComboBox { background: #F2F2F7; border: 1px solid #E8E8ED; border-radius: 8px; padding: 0 10px; }
    QComboBox::drop-down { border: none; width: 28px; }
    QComboBox::down-arrow { image: none; width: 0; height: 0; border: none; }
    QComboBox QAbstractItemView { background: white; selection-background-color: #DDEAFB; }
    QCheckBox { spacing: 10px; padding: 5px 0; }
    QPlainTextEdit { background: white; border: 1px solid #E5E5EA; border-radius: 10px; padding: 10px; }
    ''' % (family, 28 if compact else 32, 32 if compact else 38)


def apply_tone(widget, tone):
    if widget.property('tone') != tone:
        widget.setProperty('tone', tone)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
