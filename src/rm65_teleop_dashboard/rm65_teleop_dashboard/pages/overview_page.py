"""Quiet system summary; formatting never changes telemetry semantics."""
from datetime import datetime
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from ..models import summarize_system, operating_mode
from ..navigation import navigation_icon
from ..styles import apply_tone
from ..widgets import (Card, MetricTile, Page, PrimaryPanel, SettingsGroup, StatusDot,
                       adapter_live, combined_health, fresh_state, label, number, path_text)


class OverviewPage(Page):
    navigate_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__('系统状态', '双臂机器人与 VR 遥操作链路')
        self.primary = PrimaryPanel()
        top = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(7)
        text.addWidget(label('系统状态', 'cardTitle'))
        self.summary = StatusDot(role='heroState')
        text.addWidget(self.summary)
        self.summary_description = label('', 'secondary')
        text.addWidget(self.summary_description)
        top.addLayout(text, 1)
        metadata = QVBoxLayout()
        metadata.setSpacing(8)
        self.mode_meta = label('', 'secondary', Qt.AlignRight)
        self.domain_meta = label('', 'secondary', Qt.AlignRight)
        metadata.addWidget(self.mode_meta)
        metadata.addWidget(self.domain_meta)
        metadata.addStretch()
        top.addLayout(metadata)
        self.primary.body.addLayout(top)
        line = QHBoxLayout()
        line.setSpacing(28)
        self.statuses = {}
        for key, title in (('quest', 'Quest'), ('left', '左 RM65'), ('right', '右 RM65'), ('safety', '安全')):
            group = QWidget()
            column = QVBoxLayout(group)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(5)
            column.addWidget(label(title, 'secondary'))
            state = StatusDot()
            column.addWidget(state, 0, Qt.AlignLeft)
            line.addWidget(group, 1)
            self.statuses[key] = state
        self.primary.body.addLayout(line)
        self.alert = label('', 'caption')
        self.alert.setWordWrap(True)
        alert_row = QHBoxLayout()
        alert_row.setSpacing(5)
        self.check_icon = label()
        self.check_icon.setPixmap(navigation_icon('check', '#34C759').pixmap(14, 14))
        alert_row.addWidget(self.check_icon)
        alert_row.addWidget(self.alert, 1)
        self.primary.body.addLayout(alert_row)
        self.body.addWidget(self.primary)
        metrics = QHBoxLayout()
        metrics.setSpacing(16)
        self.metrics = {}
        for key, title, unit, caption in (
            ('quest', 'Quest', 'Hz', '左右控制器 · 较低值'),
            ('robot', '机器人反馈', 'Hz', '左右机械臂 · 较低值'),
            ('watchdog', 'Watchdog', '', '左右累计次数'),
            ('cycle', '最大控制周期', 'ms', '左右适配器 · 最大值')):
            tile = MetricTile(title, unit, caption)
            self.metrics[key] = tile
            metrics.addWidget(tile, 1)
        self.body.addLayout(metrics)
        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        self.current = SettingsGroup('运行摘要')
        self.details = self.current.settings
        for key, title in (('mode', '当前模式'), ('paths', '笛卡尔控制链路'),
                           ('home', '关节轨迹链路'), ('hand', '右灵巧手'), ('domain', 'ROS Domain')):
            self.details.add(key, title)
        self.runtime_text = label('', 'caption')
        self.runtime_text.setWordWrap(True)
        self.current.body.addWidget(self.runtime_text)
        bottom.addWidget(self.current, 1)
        self.events_card = Card('最近事件')
        link = label('<a href="events" style="color:#007AFF;text-decoration:none">查看全部 →</a>', 'secondary')
        link.setTextFormat(Qt.RichText)
        link.linkActivated.connect(self.navigate_requested.emit)
        self.events_card.heading.addWidget(link)
        self.recent = []
        for _ in range(4):
            row = QWidget()
            row.setMinimumHeight(44)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            time = label('', 'secondary')
            time.setFixedWidth(40)
            layout.addWidget(time)
            message = StatusDot()
            layout.addWidget(message, 0, Qt.AlignLeft)
            layout.addStretch()
            self.events_card.body.addWidget(row)
            self.recent.append((time, message))
        self.events_card.body.addStretch()
        bottom.addWidget(self.events_card, 1)
        self.body.addLayout(bottom)
        self.body.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.body.setSpacing(12 if self.compact else 24)
        self.primary.body.setSpacing(6 if self.compact else 14)
        self.primary.setMinimumHeight(168 if self.compact else 210)
        self.primary.body.setContentsMargins(18 if self.compact else 24, 10 if self.compact else 24,
                                            18 if self.compact else 24, 10 if self.compact else 24)
        self.details.set_row_height(30 if self.compact else 42)
        self.current.body.setSpacing(6 if self.compact else 12)
        self.current.setMinimumHeight(218 if self.compact else 306)
        self.events_card.body.setSpacing(4 if self.compact else 12)
        if self.compact:
            self.current.body.setContentsMargins(18, 12, 18, 12)
            self.events_card.body.setContentsMargins(18, 12, 18, 12)
        for time, message in self.recent:
            time.parentWidget().setMinimumHeight(40 if self.compact else 44)

    def update_runtime(self, runtime):
        status = runtime.system
        self.runtime_text.setText('Demo · 仅展示模拟监控数据' if runtime.demo else (
            f'本软件启动组 · {status.state.title()} · PID {status.pid}' if status.pid else '软件进程由外部管理或尚未启动'))

    def update_snapshot(self, snapshot):
        summary = summarize_system(snapshot)
        self.summary.set_state(summary, {'SYSTEM READY': '一切正常', 'DEGRADED': '需要注意',
                                         'FAULT': '存在故障', 'OFFLINE': '系统离线'}[summary])
        self.summary_description.setText('双臂机器人与 VR 遥操作链路运行正常' if summary == 'SYSTEM READY'
                                         else '查看各链路状态与安全页面了解详情')
        mode = 'Demo' if snapshot.demo else operating_mode(snapshot).title()
        self.mode_meta.setText(mode)
        self.domain_meta.setText(f'ROS Domain {snapshot.domain_id}')
        arms = (snapshot.left, snapshot.right)
        controllers = (snapshot.left_controller, snapshot.right_controller)
        quest_state = combined_health(tuple(h for c in controllers for h in (c.pose_health, c.inputs_health)))
        self.statuses['quest'].set_state(quest_state, '左右在线' if quest_state == 'ONLINE' else quest_state)
        for arm in arms:
            state = fresh_state(arm.status_health, arm.adapter.state)
            self.statuses[arm.side].set_state(state)
        self.statuses['safety'].set_state(summary, '正常' if summary == 'SYSTEM READY' else '需检查' if summary != 'OFFLINE' else '未知')
        online_rate = lambda h: h.hz if h.state == 'ONLINE' else None
        for key, values in (('quest', [online_rate(c.pose_health) for c in controllers]),
                            ('robot', [online_rate(a.robot_health) for a in arms])):
            self.metrics[key].setText(number(min(values) if all(v is not None for v in values) else None, 0))
        counts = [a.adapter.watchdog_count if adapter_live(a) else None for a in arms]
        cycles = [a.adapter.max_cycle_period_ms if adapter_live(a) else None for a in arms]
        self.metrics['watchdog'].setText(number(sum(counts) if all(v is not None for v in counts) else None, 0))
        self.metrics['cycle'].setText(number(max(cycles) if all(v is not None for v in cycles) else None, 1))
        self.details.set_value('mode', mode)
        self.details.set_value('domain', snapshot.domain_id)
        self.details.set_value('paths', ' / '.join(f'{side} {path_text(a, a.adapter.command_path_ready)}' for side, a in zip(('左', '右'), arms)))
        self.details.set_value('home', ' / '.join(f'{side} {path_text(a, a.adapter.home_command_path_ready)}' for side, a in zip(('左', '右'), arms)))
        hand = snapshot.linkerhand
        self.details.set_value('hand', fresh_state(hand.health, hand.state).title())
        events = list(reversed(snapshot.events))[:4]
        names = {'linkerhand': '右灵巧手', 'left_arm': '左机械臂', 'right_arm': '右机械臂',
                 'left_status': '左臂状态', 'right_status': '右臂状态', 'left_joints': '左臂关节',
                 'right_joints': '右臂关节', 'system': '系统', 'safety': '安全'}
        for index, (time, widget) in enumerate(self.recent):
            if index < len(events):
                event = events[index]
                time.setText(f'{datetime.fromtimestamp(event.time_s):%H:%M}')
                message = f'{names.get(event.source, "链路状态")} · {event.message}'
                widget.set_state('FAULT' if event.level == 'ERROR' else 'HOMING' if event.level == 'WARN' else 'UNKNOWN',
                                 message if len(message) < 32 else message[:31] + '…')
                widget.setToolTip(f'{event.source} · {event.message}')
            else:
                time.setText('')
                widget.set_state('UNKNOWN', '暂无更多事件' if index == len(events) else '')
            widget.dot.setVisible(index < len(events))
        reasons = [a.adapter.parse_error or a.adapter.reason for a in arms if a.adapter.parse_error or a.adapter.reason]
        if snapshot.monitor_error:
            reasons.append(snapshot.monitor_error)
        message = ' · '.join(reasons)
        self.alert.setText(message[:150] if message else '没有需要处理的问题' if summary == 'SYSTEM READY'
                           else '等待系统数据；详情请查看安全页面。')
        self.check_icon.setVisible(not message and summary == 'SYSTEM READY')
        self.alert.setToolTip(message)
        apply_tone(self.alert, 'red' if summary == 'FAULT' else 'orange' if message else 'green' if summary == 'SYSTEM READY' else 'grey')
