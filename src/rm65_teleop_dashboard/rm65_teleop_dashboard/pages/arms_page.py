"""Selected-arm details, with raw quaternion and bridge values disclosed on demand."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from ..styles import apply_tone
from ..widgets import (Card, Disclosure, JointBar, Page, SegmentControl, SettingsList,
                       StatusDot, ValueTriple, adapter_live, age_text, divider,
                       fresh_state, label, number, path_text)


class ArmPanel(QWidget):
    def __init__(self, side):
        super().__init__()
        self.side = side
        body = QVBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(20)
        heading = QHBoxLayout()
        heading.addWidget(label(side.title() + ' Arm', 'section'))
        self.state_label = StatusDot()
        heading.addWidget(self.state_label)
        heading.addStretch()
        heading.addWidget(label('Cartesian teleoperation', 'secondary'))
        body.addLayout(heading)
        pose = Card('末端位姿')
        self.position = ValueTriple(('X', 'Y', 'Z'), 'm')
        self.orientation = ValueTriple(('Roll', 'Pitch', 'Yaw'), '°')
        pose.body.addWidget(self.position)
        pose.body.addWidget(divider())
        pose.body.addWidget(self.orientation)
        self.details = Disclosure()
        self.quaternion = label('', 'secondary')
        self.target = label('', 'secondary')
        self.target.setWordWrap(True)
        self.details.body.addWidget(self.quaternion)
        self.details.body.addWidget(self.target)
        pose.body.addWidget(self.details)
        body.addWidget(pose)
        lower = QHBoxLayout()
        lower.setSpacing(20)
        joints = Card('关节')
        grid = QGridLayout()
        grid.setVerticalSpacing(22)
        grid.setHorizontalSpacing(24)
        self.joint_rows = []
        for index in range(6):
            grid.addWidget(label(f'J{index + 1}', 'secondary'), index, 0)
            value = label('—', 'jointValue')
            value.setMinimumWidth(62)
            grid.addWidget(value, index, 1)
            bar = JointBar()
            grid.addWidget(bar, index, 2)
            self.joint_rows.append((value, bar))
        grid.setColumnStretch(2, 1)
        joints.body.addLayout(grid)
        joints.body.addStretch()
        joints.body.addWidget(label('显示范围 ±180° · 仅用于可视化', 'caption'))
        lower.addWidget(joints, 1)
        health = Card('数据状态')
        self.health = SettingsList()
        for name in ('Pose', 'Input', 'Robot', 'Joint'):
            self.health.add(name, name)
        self.deadman = self.health.add('deadman', 'Grip', status=True)
        self.cart = self.health.add('cart', 'Cartesian Path', status=True)
        self.home = self.health.add('home', 'Home Path', status=True)
        health.body.addWidget(self.health)
        lower.addWidget(health, 1)
        body.addLayout(lower)
        self.reason = label('', 'alert')
        self.reason.setWordWrap(True)
        body.addWidget(self.reason)

    def update_arm(self, arm, controller):
        status = arm.adapter
        state = fresh_state(arm.status_health, status.state)
        self.state_label.set_state(state)
        self.position.set_values(arm.robot_pose.position)
        self.orientation.set_values(arm.robot_pose.rpy_deg, 1)
        self.quaternion.setText('Quaternion · ' + '   '.join(
            f'{key} {number(value, 4)}' for key, value in zip(
                ('qx', 'qy', 'qz', 'qw'), arm.robot_pose.quaternion or (None,) * 4)))
        self.target.setText('Quest bridge target · ' + ' / '.join(
            number(v, 3) for v in arm.target_pose.position or (None,) * 3)
            + f' m · {age_text(arm.target_health)}')
        for (value_label, bar), value in zip(self.joint_rows, arm.joints_deg):
            value_label.setText(number(value, 1, '°'))
            bar.set_value(value)
        for name, stream in (('Pose', controller.pose_health), ('Input', controller.inputs_health),
                             ('Robot', arm.robot_health), ('Joint', arm.joints_health)):
            self.health.set_value(name, age_text(stream))
            self.health.fields[name].setToolTip(f'{stream.state} · {number(stream.hz, 1)} Hz\n{stream.error}')
        deadman = ('Pressed' if status.deadman_pressed is True else 'Released'
                   if status.deadman_pressed is False else 'Unknown') if adapter_live(arm) else state
        self.deadman.set_state('PRESSED' if deadman == 'Pressed' else state if not adapter_live(arm) else 'UNKNOWN', deadman)
        for widget, ready in ((self.cart, status.command_path_ready), (self.home, status.home_command_path_ready)):
            text = path_text(arm, ready)
            widget.set_state(text.upper(), text)
        reason = status.parse_error or status.reason or arm.joints_error or arm.robot_pose.error
        self.reason.setText(reason)
        self.reason.setVisible(bool(reason))
        apply_tone(self.reason, 'red' if status.parse_error or status.state == 'FAULT' else 'orange')


class ArmsPage(Page):
    def __init__(self):
        super().__init__('双臂', '查看单臂位姿、关节与数据状态')
        self.selector = SegmentControl((('left', 'Left Arm'), ('right', 'Right Arm')))
        self.header.addWidget(self.selector)
        self.arms = {side: ArmPanel(side) for side in ('left', 'right')}
        self.stack = QStackedWidget()
        for arm in self.arms.values():
            self.stack.addWidget(arm)
        self.selector.changed.connect(lambda side: self.stack.setCurrentIndex(0 if side == 'left' else 1))
        self.body.addWidget(self.stack)
        self.body.addStretch(1)

    def update_snapshot(self, snapshot):
        for side, panel in self.arms.items():
            panel.update_arm(getattr(snapshot, side), getattr(snapshot, side + '_controller'))
