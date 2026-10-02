"""A five-second system summary with technical detail on separate pages."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout
from ..models import summarize_system
from ..styles import apply_tone
from ..widgets import (Card, Page, RobotOverviewWidget, StatusDot, adapter_live,
                       age_text, combined_health, divider, fresh_state, label, number)


class OverviewPage(Page):
    def __init__(self):
        super().__init__('系统状态', '双臂机器人与 VR 遥操作链路')
        self.summary = StatusDot()
        self.header.addWidget(self.summary, 0, Qt.AlignVCenter)
        self.hero = Card()
        self.hero.body.setContentsMargins(34, 24, 40, 24)
        row = QHBoxLayout()
        row.setSpacing(54)
        self.robot = RobotOverviewWidget()
        row.addWidget(self.robot, 6)
        details = QVBoxLayout()
        details.setSpacing(18)
        details.addStretch()
        states = QGridLayout()
        states.setHorizontalSpacing(48)
        states.setVerticalSpacing(14)
        self.arm_states = []
        for index, side in enumerate(('Left Arm', 'Right Arm')):
            states.addWidget(label(side, 'secondary'), index, 0)
            state = StatusDot(role='heroState')
            self.arm_states.append(state)
            states.addWidget(state, index, 1)
        details.addLayout(states)
        details.addSpacing(8)
        details.addWidget(divider())
        self.connections = {}
        for key, title in (('quest', 'Quest'), ('ros', 'ROS 2'), ('hand', 'LinkerHand')):
            line = QHBoxLayout()
            line.addWidget(label(title, 'secondary'))
            line.addStretch()
            status = StatusDot()
            self.connections[key] = status
            line.addWidget(status)
            details.addLayout(line)
        details.addStretch()
        row.addLayout(details, 4)
        self.hero.body.addLayout(row, 1)
        self.body.addWidget(self.hero)
        metrics = QHBoxLayout()
        metrics.setSpacing(18)
        self.metrics = {}
        self.metric_cards = []
        for key, title, note in (('quest', 'Quest', '控制器追踪'),
                                 ('robot', 'Robot Feedback', '机械臂实时反馈'),
                                 ('watchdog', 'Watchdog', '双臂累计触发'),
                                 ('cycle', 'Control Cycle', '最大控制周期')):
            card = Card()
            card.body.setSpacing(7)
            card.body.addWidget(label(title, 'secondary'))
            value = label('—', 'metric')
            card.body.addWidget(value)
            card.body.addWidget(label(note, 'caption'))
            self.metrics[key] = value
            self.metric_cards.append(card)
            metrics.addWidget(card, 1)
        self.body.addLayout(metrics)
        self.clear_message = label('没有需要处理的问题', 'secondary')
        self.clear_message.setContentsMargins(4, 8, 0, 8)
        self.alert = label('', 'alert')
        self.alert.setWordWrap(True)
        self.body.addWidget(self.clear_message)
        self.body.addWidget(self.alert)
        self.body.addStretch(1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'hero'):
            self.hero.setFixedHeight(280 if self.compact else 390)
            for card in self.metric_cards:
                card.body.setContentsMargins(22, 17 if self.compact else 22, 22, 17 if self.compact else 22)

    def update_snapshot(self, snapshot):
        summary = summarize_system(snapshot)
        self.summary.set_state(summary, {'SYSTEM READY': '系统正常', 'DEGRADED': '需要注意',
                                        'FAULT': '存在故障', 'OFFLINE': '系统离线'}[summary])
        arms = (snapshot.left, snapshot.right)
        for widget, arm in zip(self.arm_states, arms):
            widget.set_state(fresh_state(arm.status_health, arm.adapter.state))
        self.robot.update_states(*(fresh_state(arm.status_health, arm.adapter.state) for arm in arms))
        controllers = (snapshot.left_controller, snapshot.right_controller)
        quest_state = combined_health([health for controller in controllers
                                       for health in (controller.pose_health, controller.inputs_health)])
        self.connections['quest'].set_state(quest_state, quest_state.title())
        self.connections['quest'].setToolTip('\n'.join(
            f'{side}: {number(controller.pose_health.hz, 1)} Hz · {age_text(controller.pose_health)} · input {age_text(controller.inputs_health)}'
            for side, controller in zip(('Left', 'Right'), controllers)))
        ros_state = 'FAULT' if snapshot.monitor_error else 'ONLINE' if snapshot.node_count is not None else 'UNKNOWN'
        self.connections['ros'].set_state(ros_state, ros_state.title())
        self.connections['ros'].setToolTip(f'Domain {snapshot.domain_id} · {number(snapshot.node_count, 0)} discovered nodes')
        hand = snapshot.linkerhand
        hand_state = fresh_state(hand.health, hand.state)
        self.connections['hand'].set_state(hand_state, hand_state.replace('_', ' ').title())
        self.connections['hand'].setToolTip(f'{hand.hand_toggle_state} · {age_text(hand.health)}')
        quest_rates = [c.pose_health.hz for c in controllers if c.pose_health.state == 'ONLINE']
        robot_rates = [a.robot_health.hz for a in arms if a.robot_health.state == 'ONLINE']
        # One combined number is accompanied by per-side hover detail. Missing sides
        # never masquerade as a healthy aggregate; the summary above remains degraded.
        self.metrics['quest'].setText(number(min(quest_rates) if len(quest_rates) == 2 else None, 0, ' Hz'))
        self.metrics['robot'].setText(number(min(robot_rates) if len(robot_rates) == 2 else None, 0, ' Hz'))
        self.metrics['robot'].setToolTip('\n'.join(
            f'{a.side.title()}: TCP {number(a.robot_health.hz, 1)} Hz · {age_text(a.robot_health)}; joints {number(a.joints_health.hz, 1)} Hz · {age_text(a.joints_health)}'
            for a in arms))
        counts = [a.adapter.watchdog_count if adapter_live(a) else None for a in arms]
        cycles = [a.adapter.max_cycle_period_ms if adapter_live(a) else None for a in arms]
        self.metrics['watchdog'].setText(number(sum(counts) if all(v is not None for v in counts) else None, 0))
        self.metrics['watchdog'].setToolTip(f'Left {number(counts[0], 0)} · Right {number(counts[1], 0)}')
        self.metrics['cycle'].setText(number(max(cycles) if all(v is not None for v in cycles) else None, 1, ' ms'))
        reasons = [snapshot.monitor_error] if snapshot.monitor_error else []
        for arm in arms:
            reason = arm.adapter.parse_error or arm.adapter.reason or arm.joints_error or arm.robot_pose.error
            if reason:
                reasons.append(f'{arm.side.title()} Arm · {reason}')
        if hand.parse_error or hand.error:
            reasons.append(f'LinkerHand · {hand.parse_error or hand.error}')
        message = '\n'.join(reasons)
        if not message and summary != 'SYSTEM READY':
            message = '等待系统数据连接。' if summary == 'OFFLINE' else '部分数据或链路需要检查，请在对应页面查看详情。'
        self.alert.setText(message)
        apply_tone(self.alert, 'red' if summary == 'FAULT' else 'orange')
        self.alert.setVisible(bool(message))
        self.clear_message.setVisible(not message)
