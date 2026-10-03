"""Compact operational summary; technical detail belongs on dedicated pages."""
from datetime import datetime
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout
from ..models import summarize_system, operating_mode
from ..styles import apply_tone
from ..widgets import Card, Page, SettingsList, StatusDot, adapter_live, combined_health, fresh_state, label, number, path_text


class OverviewPage(Page):
    def __init__(self):
        super().__init__('系统状态', '双臂机器人与 VR 遥操作链路')
        summaries = QHBoxLayout()
        summaries.setSpacing(16)
        self.statuses = {}
        for key, title, count in (('system', '系统状态', 1), ('quest', 'Quest', 2),
                                   ('arms', 'RM65', 2), ('safety', 'Safety', 1)):
            card = Card(title)
            card.body.setSpacing(12)
            states = [StatusDot() for _ in range(count)]
            for state in states:
                card.body.addWidget(state)
            self.statuses[key] = states
            summaries.addWidget(card, 1)
        self.summary = self.statuses['system'][0]
        self.body.addLayout(summaries)
        metrics = Card()
        row = QHBoxLayout()
        row.setSpacing(28)
        self.metrics = {}
        for key, title in (('quest', 'Quest Rate'), ('robot', 'Robot Feedback'),
                           ('watchdog', 'Watchdog'), ('cycle', 'Max Cycle')):
            column = QVBoxLayout()
            column.setSpacing(8)
            column.addWidget(label(title, 'secondary'))
            self.metrics[key] = label('—', 'metric')
            column.addWidget(self.metrics[key])
            row.addLayout(column, 1)
        metrics.body.addLayout(row)
        self.body.addWidget(metrics)
        bottom = QHBoxLayout()
        bottom.setSpacing(18)
        current = Card('当前运行摘要')
        self.runtime_text = label('软件进程 · 未由本软件启动', 'secondary')
        current.body.addWidget(self.runtime_text)
        self.details = SettingsList()
        for key, title in (('mode', '监控数据'), ('paths', 'Cartesian path'),
                           ('hand', '右灵巧手'), ('domain', 'ROS Domain')):
            self.details.add(key, title)
        current.body.addWidget(self.details)
        bottom.addWidget(current, 1)
        recent = Card('最近事件')
        self.recent = []
        for _ in range(4):
            line = label('—', 'secondary')
            line.setWordWrap(True)
            recent.body.addWidget(line)
            self.recent.append(line)
        recent.body.addStretch()
        recent.body.addWidget(label('完整记录与筛选请前往“事件”。', 'caption'))
        bottom.addWidget(recent, 1)
        self.body.addLayout(bottom)
        self.alert = label('', 'secondary')
        self.alert.setWordWrap(True)
        self.body.addWidget(self.alert)
        self.body.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for card in self.findChildren(Card):
            card.body.setContentsMargins(22, 15 if self.compact else 24, 22, 15 if self.compact else 24)
            card.body.setSpacing(10 if self.compact else 18)

    def update_runtime(self, runtime):
        status = runtime.system
        text = 'Demo · 进程管理未启用' if runtime.demo else (
            f'本软件启动组 · {status.state.title()} · PID {status.pid}' if status.pid else '软件进程 · 未由本软件启动')
        self.runtime_text.setText(text)

    def update_snapshot(self, snapshot):
        summary = summarize_system(snapshot)
        self.summary.set_state(summary, {'SYSTEM READY': '系统正常', 'DEGRADED': '需要注意',
                                         'FAULT': '存在故障', 'OFFLINE': '系统离线'}[summary])
        arms = (snapshot.left, snapshot.right)
        controllers = (snapshot.left_controller, snapshot.right_controller)
        for index, (arm, controller) in enumerate(zip(arms, controllers)):
            side = 'Left' if index == 0 else 'Right'
            state = combined_health((controller.pose_health, controller.inputs_health))
            self.statuses['quest'][index].set_state(state, f'{side} · {state.title()}')
            state = fresh_state(arm.status_health, arm.adapter.state)
            self.statuses['arms'][index].set_state(state, f'{side} · {state}')
        self.statuses['safety'][0].set_state(summary, 'Normal' if summary == 'SYSTEM READY' else '需检查' if summary != 'OFFLINE' else 'Unknown')
        online_rate = lambda h: h.hz if h.state == 'ONLINE' else None
        quest_rates = [online_rate(c.pose_health) for c in controllers]
        robot_rates = [online_rate(a.robot_health) for a in arms]
        for key, values in (('quest', quest_rates), ('robot', robot_rates)):
            self.metrics[key].setText(number(min(values) if all(v is not None for v in values) else None, 0, ' Hz'))
        counts = [a.adapter.watchdog_count if adapter_live(a) else None for a in arms]
        cycles = [a.adapter.max_cycle_period_ms if adapter_live(a) else None for a in arms]
        self.metrics['watchdog'].setText(number(sum(counts) if all(v is not None for v in counts) else None, 0))
        self.metrics['cycle'].setText(number(max(cycles) if all(v is not None for v in cycles) else None, 1, ' ms'))
        self.details.set_value('mode', 'Demo Data' if snapshot.demo else operating_mode(snapshot).title())
        self.details.set_value('domain', snapshot.domain_id)
        self.details.set_value('paths', ' / '.join(path_text(a, a.adapter.command_path_ready) for a in arms))
        hand = snapshot.linkerhand
        self.details.set_value('hand', fresh_state(hand.health, hand.state).title())
        events = list(reversed(snapshot.events))[:4]
        for index, widget in enumerate(self.recent):
            if index < len(events):
                event = events[index]
                message = event.message if len(event.message) <= 100 else event.message[:100] + '…'
                widget.setText(f'{datetime.fromtimestamp(event.time_s):%H:%M}   {event.source}   {message}')
                widget.setToolTip(event.message)
                apply_tone(widget, 'red' if event.level == 'ERROR' else 'orange' if event.level == 'WARN' else 'grey')
            else:
                widget.setText('暂无更多事件' if index == len(events) else '')
        reasons = [a.adapter.parse_error or a.adapter.reason for a in arms if a.adapter.parse_error or a.adapter.reason]
        if snapshot.monitor_error:
            reasons.append(snapshot.monitor_error)
        message = ' · '.join(reasons)
        self.alert.setText(message[:200] if message else '没有需要处理的问题' if summary == 'SYSTEM READY' else '等待系统数据；详情请查看对应页面。')
        self.alert.setToolTip(message)
        apply_tone(self.alert, 'red' if summary == 'FAULT' else 'orange' if message else 'grey')
