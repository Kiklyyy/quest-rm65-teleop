"""Controller telemetry and existing button mappings, never input commands."""
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QHBoxLayout, QWidget
from ..styles import apply_tone
from ..widgets import (Card, Page, StatusDot, ValueTriple, age_text, combined_health,
                       divider, label, number, progress)


class ButtonIndicator(QWidget):
    def __init__(self, text):
        super().__init__()
        self.text = text
        self.pressed = False
        self.available = False
        self.setFixedSize(32, 32)
        self.setToolTip('Physical button input · read only')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#007AFF' if self.pressed else '#E5E5EA'))
        painter.drawEllipse(QRectF(0, 0, 32, 32))
        painter.setPen(QColor('white' if self.pressed else '#6E6E73'))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text if self.available else '—')


class ControllerCard(Card):
    def __init__(self, side):
        super().__init__('左控制器' if side == 'left' else '右控制器')
        self.side = side
        self.state_label = StatusDot()
        self.heading.addWidget(self.state_label)
        self.body.addWidget(label('L' if side == 'left' else 'R', 'metric'))
        self.position = ValueTriple(('X', 'Y', 'Z'), 'm')
        self.orientation = ValueTriple(('Roll', 'Pitch', 'Yaw'), '°')
        for widget in self.position.values + self.orientation.values:
            widget.setProperty('role', 'controllerValue')
        self.body.addWidget(self.position)
        self.body.addWidget(self.orientation)
        self.timing = label('', 'secondary')
        self.input_timing = label('', 'secondary')
        self.body.addWidget(self.timing)
        self.body.addWidget(self.input_timing)
        self.body.addWidget(divider())
        self.analogs = []
        for name in ('Grip', 'Index'):
            line = QHBoxLayout()
            line.addWidget(label(name))
            line.addStretch()
            value = label('—', 'secondary')
            line.addWidget(value)
            self.body.addLayout(line)
            bar = progress()
            self.body.addWidget(bar)
            self.analogs.append((bar, value))
        buttons = QHBoxLayout()
        buttons.setSpacing(14)
        self.buttons = [ButtonIndicator(name) for name in (('X', 'Y') if side == 'left' else ('A', 'B'))]
        for button in self.buttons:
            buttons.addWidget(button)
        buttons.addStretch()
        self.body.addLayout(buttons)
        self.body.addWidget(divider())
        self.body.addWidget(label('控制映射', 'secondary'))
        mapping = ('Grip → Cartesian Teleop\nX → Right Preset 1\nY → Left Home' if side == 'left' else
                   'Grip → Cartesian Teleop\nIndex → LinkerHand Toggle\nA → Right Preset 2\nB → Right Preset 3')
        mapping_label = label(mapping, 'secondary')
        mapping_label.setWordWrap(True)
        self.body.addWidget(mapping_label)
        self.body.addStretch()
        self.error = label('', 'alert')
        self.error.setWordWrap(True)
        self.body.addWidget(self.error)

    def update_controller(self, controller):
        health = combined_health((controller.pose_health, controller.inputs_health))
        self.state_label.set_state(health, 'Connected' if health == 'ONLINE' else health.title())
        self.position.set_values(controller.pose.position)
        self.orientation.set_values(controller.pose.rpy_deg, 1)
        self.timing.setText(f'Tracking · {number(controller.pose_health.hz, 1)} Hz · {age_text(controller.pose_health)}')
        self.input_timing.setText(f'Inputs · {age_text(controller.inputs_health)}')
        live = controller.inputs_health.state == 'ONLINE'
        for (bar, widget), value in zip(self.analogs, (controller.grip, controller.trigger)):
            bar.setValue(round(value * 1000) if value is not None else 0)
            apply_tone(bar, 'blue' if live else 'grey')
            widget.setText(number(value * 100 if value is not None else None, 0, '%'))
        for widget, pressed in zip(self.buttons, (controller.button_lower, controller.button_upper)):
            widget.available = live and pressed is not None
            widget.pressed = live and pressed is True
            widget.update()
        error = controller.pose.error or controller.inputs_health.error
        self.error.setText(error)
        self.error.setVisible(bool(error))


class ControllersPage(Page):
    def __init__(self):
        super().__init__('VR 控制器', '追踪姿态、模拟输入与按键状态')
        row = QHBoxLayout()
        row.setSpacing(22)
        self.controllers = {side: ControllerCard(side) for side in ('left', 'right')}
        for card in self.controllers.values():
            row.addWidget(card, 1)
        self.body.addLayout(row)
        self.body.addWidget(label('映射由现有遥操作系统处理，当前页面仅显示输入。', 'caption'))
        self.body.addStretch(1)

    def update_snapshot(self, snapshot):
        for side, card in self.controllers.items():
            card.update_controller(getattr(snapshot, side + '_controller'))
