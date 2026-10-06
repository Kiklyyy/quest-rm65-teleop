"""Presentation primitives shared by monitoring and runtime pages."""
import math
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
                            QScrollArea, QSizePolicy, QToolButton, QVBoxLayout, QWidget)
from .models import status_tone
from .styles import COLORS, apply_tone


def number(value, decimals=1, suffix=''):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return '—'
    try:
        return f'{value:.{decimals}f}{suffix}' if math.isfinite(value) else '—'
    except OverflowError:
        return '—'


def label(text='', role=None, alignment=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    if role:
        widget.setProperty('role', role)
    if alignment is not None:
        widget.setAlignment(alignment)
    return widget


def age_text(health):
    age = number(health.age_ms, 0, ' ms')
    return age if health.state == 'ONLINE' else f'{fresh_state(health, "")} · {age}'


def fresh_state(health, state):
    return state if health.state == 'ONLINE' else 'LOST' if health.state == 'OFFLINE' else health.state


def combined_health(healths):
    states = [item.state for item in healths]
    if 'INVALID' in states:
        return 'INVALID'
    if all(state == 'ONLINE' for state in states):
        return 'ONLINE'
    return 'OFFLINE' if all(state == 'OFFLINE' for state in states) else 'STALE'


def adapter_live(arm):
    return arm.status_health.state == 'ONLINE' and not arm.adapter.parse_error


def path_text(arm, ready):
    if not adapter_live(arm):
        return fresh_state(arm.status_health, 'DATA_ERROR')
    return 'Ready' if ready is True else 'Blocked' if ready is False else 'Unknown'


def divider():
    widget = QFrame()
    widget.setProperty('role', 'divider')
    widget.setFixedHeight(1)
    return widget


class StatusDot(QWidget):
    """Color is confined to an eight-pixel dot; status text stays neutral."""
    def __init__(self, state='UNKNOWN', text=None, role=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.dot = QWidget()
        self.dot.setFixedSize(8, 8)
        self.dot.installEventFilter(self)
        self.text_label = label('', role)
        layout.addWidget(self.dot)
        layout.addWidget(self.text_label)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self.set_state(state, text)

    def eventFilter(self, watched, event):
        from PyQt5.QtCore import QEvent
        if watched is self.dot and event.type() == QEvent.Paint:
            painter = QPainter(self.dot)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(COLORS[self.tone]))
            painter.drawEllipse(QRectF(0, 0, 8, 8))
            return True
        return super().eventFilter(watched, event)

    def set_state(self, state, text=None):
        self.state = str(state)
        self.tone = status_tone(str(state).upper())
        self.text_label.setText(str(state) if text is None else text)
        self.dot.update()

    def text(self):
        return self.text_label.text()


class Card(QFrame):
    def __init__(self, title='', parent=None):
        super().__init__(parent)
        self.setProperty('role', 'card')
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 20, 20, 20)
        self.body.setSpacing(16)
        self.heading = QHBoxLayout()
        self.heading.setSpacing(12)
        if title:
            self.heading.addWidget(label(title, 'section'))
        self.heading.addStretch()
        if title:
            self.body.addLayout(self.heading)

    def set_compact(self, compact):
        padding = 18 if compact else 20
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(12 if compact else 16)


class PrimaryPanel(Card):
    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self.setProperty('role', 'primaryPanel')
        self.set_compact(False)

    def set_compact(self, compact):
        padding = 18 if compact else 24
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(12 if compact else 16)


class StyledComboBox(QComboBox):
    """Draw a local vector chevron, independent of platform glyph support."""
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor('#6E6E73'), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        x, y = self.width() - 17, self.height() / 2
        painter.drawLine(QPointF(x - 4, y - 2), QPointF(x, y + 2))
        painter.drawLine(QPointF(x, y + 2), QPointF(x + 4, y - 2))


class MetricTile(Card):
    def __init__(self, title, unit='', caption='', parent=None):
        super().__init__(parent=parent)
        self.setProperty('role', 'metricTile')
        self.body.addWidget(label(title, 'secondary'))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        self.value = label('—', 'metric')
        self.unit = label(unit, 'metricUnit')
        row.addWidget(self.value, 0, Qt.AlignBaseline)
        row.addWidget(self.unit, 0, Qt.AlignBaseline)
        row.addStretch()
        self.body.addLayout(row)
        self.body.addWidget(label(caption, 'caption'))
        self.set_compact(False)

    def set_compact(self, compact):
        padding = 14 if compact else 18
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(4 if compact else 7)
        self.setMinimumHeight(106 if compact else 130)

    def setText(self, text):
        self.value.setText(text)


class Page(QScrollArea):
    """Constrained readable content with scrolling only when a page needs it."""
    def __init__(self, title, subtitle='', parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        wrapper = QWidget()
        self.outer = QHBoxLayout(wrapper)
        self.outer.setContentsMargins(32, 28, 32, 28)
        self.content = QWidget()
        self.content.setMaximumWidth(1480)
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(24)
        self.body.setAlignment(Qt.AlignTop)
        self.outer.addStretch(1)
        self.outer.addWidget(self.content, 100)
        self.outer.addStretch(1)
        self.setWidget(wrapper)
        self.header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(6)
        titles.addWidget(label(title, 'pageTitle'))
        if subtitle:
            titles.addWidget(label(subtitle, 'subtitle'))
        self.header.addLayout(titles)
        self.header.addStretch()
        self.body.addLayout(self.header)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.compact = self.window().width() < 1600
        self.outer.setContentsMargins(20 if self.compact else 32, 18 if self.compact else 28,
                                     20 if self.compact else 32, 18 if self.compact else 28)
        self.body.setSpacing(12 if self.compact else 24)
        for card in self.findChildren(Card):
            card.set_compact(self.compact)


class ValueTriple(QWidget):
    def __init__(self, names, unit, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(5)
        self.values = []
        for index, name in enumerate(names):
            grid.addWidget(label(name, 'secondary'), 0, index)
            value = label('—', 'value')
            self.values.append(value)
            grid.addWidget(value, 1, index)
            grid.setColumnStretch(index, 1)
        grid.addWidget(label(unit, 'secondary'), 1, 3, Qt.AlignBottom)

    def set_values(self, values, decimals=3):
        for index, widget in enumerate(self.values):
            widget.setText(number(values[index] if values else None, decimals))


class SegmentControl(QFrame):
    changed = pyqtSignal(str)

    def __init__(self, choices, parent=None):
        super().__init__(parent)
        self.setProperty('role', 'segment')
        row = QHBoxLayout(self)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)
        self.buttons = {}
        for key, title in choices:
            button = QToolButton()
            button.setProperty('role', 'segment')
            button.setText(title)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, key=key: self.select(key))
            row.addWidget(button)
            self.buttons[key] = button
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setFixedHeight(36)
        self.select(next(iter(self.buttons)), emit=False)

    def select(self, key, emit=True):
        if key not in self.buttons:
            raise ValueError(key)
        self.current = key
        for name, button in self.buttons.items():
            button.setChecked(name == key)
        if emit:
            self.changed.emit(key)


class Disclosure(QWidget):
    def __init__(self, title='详细信息', parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.toggle = QToolButton()
        self.toggle.setProperty('role', 'disclosure')
        self.toggle.setText(title)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.RightArrow)
        self.toggle.setCheckable(True)
        self.toggle.toggled.connect(self._toggle)
        layout.addWidget(self.toggle, 0, Qt.AlignLeft)
        self.content = QWidget()
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        layout.addWidget(self.content)
        self.content.hide()

    def _toggle(self, checked):
        self.content.setVisible(checked)
        self.toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)


class SettingsList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        self.fields = {}

    def add(self, key, title, status=False):
        if self.fields:
            self.body.addWidget(divider())
        container = QWidget()
        container.setMinimumHeight(42)
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(14)
        row.addWidget(label(title, 'secondary'))
        row.addStretch()
        widget = StatusDot() if status else label('—')
        row.addWidget(widget)
        self.body.addWidget(container)
        self.fields[key] = widget
        return widget

    def set_value(self, key, text, state=None):
        widget = self.fields[key]
        if isinstance(widget, StatusDot):
            widget.set_state(state or text, text)
        else:
            widget.setText(str(text))

    def set_row_height(self, height):
        for index in range(self.body.count()):
            row = self.body.itemAt(index).widget()
            if row and row.layout():
                row.setMinimumHeight(height)
                row.layout().setContentsMargins(0, 4, 0, 4)


class SettingsGroup(Card):
    """One surface with divided rows, rather than nested cards."""
    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self.setProperty('role', 'settingsGroup')
        self.settings = SettingsList()
        self.body.addWidget(self.settings)


class TimelineStep(QWidget):
    def __init__(self, title, first=False, last=False):
        super().__init__()
        self.first, self.last = first, last
        self.tone = 'grey'
        self.setFixedHeight(38)
        row = QHBoxLayout(self)
        row.setContentsMargins(26, 0, 0, 0)
        row.addWidget(label(title))
        row.addStretch()
        self.state_label = label('—', 'secondary')
        row.addWidget(self.state_label)

    def set_state(self, state, text=None):
        self.tone = status_tone(state)
        self.state_label.setText(text if text is not None else state)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self.height() / 2
        painter.setPen(QPen(QColor('#D1D1D6'), 1))
        painter.drawLine(QPointF(6, center if self.first else 0),
                         QPointF(6, center if self.last else self.height()))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLORS[self.tone]))
        painter.drawEllipse(QPointF(6, center), 5, 5)


class RuntimeTimeline(QWidget):
    def __init__(self, entries):
        super().__init__()
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.steps = {}
        for index, (key, title) in enumerate(entries):
            step = TimelineStep(title, index == 0, index == len(entries) - 1)
            body.addWidget(step)
            self.steps[key] = step


class JointBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = None
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value):
        self.value = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#E5E5EA'))
        painter.drawRoundedRect(QRectF(0, 3, self.width(), 4), 2, 2)
        if self.value is not None and math.isfinite(self.value):
            center = self.width() / 2
            length = max(-180, min(180, self.value)) / 180 * center
            painter.setBrush(QColor(COLORS['blue']))
            painter.drawRoundedRect(QRectF(min(center, center + length), 3, max(1, abs(length)), 4), 2, 2)


def progress():
    widget = QProgressBar()
    widget.setRange(0, 1000)
    widget.setTextVisible(False)
    widget.setFixedHeight(5)
    return widget


class RobotOverviewWidget(QWidget):
    """Original six-joint schematic, deliberately not a kinematics display."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.states = ('UNKNOWN', 'UNKNOWN')
        self.setMinimumSize(200, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setToolTip('双 RM65 · 每臂六关节的状态示意，非实时运动学模型')

    def update_states(self, left, right):
        if self.states != (left, right):
            self.states = (left, right)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = min(self.width() / 520, self.height() / 330)
        p.translate((self.width() - 520 * scale) / 2, (self.height() - 330 * scale) / 2)
        p.scale(scale, scale)
        p.setPen(QPen(QColor('#C7C7CC'), 2))
        p.setBrush(QColor('#F2F2F4'))
        p.drawRoundedRect(QRectF(238, 218, 44, 64), 9, 9)
        p.drawRoundedRect(QRectF(209, 280, 102, 10), 5, 5)
        paths = (
            [(241, 226), (186, 209), (147, 150), (163, 102), (130, 70), (112, 52)],
            [(279, 226), (334, 209), (373, 150), (357, 102), (390, 70), (408, 52)],
        )
        for points, state in zip(paths, self.states):
            fault = state in ('FAULT', 'DATA_ERROR', 'INVALID')
            color = QColor('#FFB9B3' if fault else '#CBD5DF' if state == 'ACTIVE' else '#C7C7CC')
            path = QPainterPath(QPointF(*points[0]))
            for point in points[1:]:
                path.lineTo(QPointF(*point))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(color, 17, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            p.setPen(QPen(QColor('#EFF5FC' if state == 'ACTIVE' else '#F2F2F4'), 10,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            p.setPen(QPen(QColor('#D97870' if fault else '#8E8E93'), 1.6))
            p.setBrush(QColor('white'))
            for index, point in enumerate(points):
                radius = 8 if index < 3 else 5.5
                p.drawEllipse(QPointF(*point), radius, radius)
            x, y = points[-1]
            p.setPen(QPen(QColor('#8E8E93'), 2, Qt.SolidLine, Qt.RoundCap))
            sign = -1 if x < 260 else 1
            p.drawLine(QPointF(x - 5, y - 4), QPointF(x - 5 + 7 * sign, y - 21))
            p.drawLine(QPointF(x + 5, y - 4), QPointF(x + 5 + 7 * sign, y - 21))
