"""Seven right-hand channels, distinct from the robot's six joints."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout
from ..models import HAND_CHANNELS
from ..styles import apply_tone
from ..widgets import (Card, Disclosure, Page, SettingsList, StatusDot, age_text,
                       divider, fresh_state, label, number, progress)


class LinkerHandPage(Page):
    def __init__(self):
        super().__init__('右灵巧手', 'Right LinkerHand L7')
        self.state_label = StatusDot()
        self.header.addWidget(self.state_label)
        card = Card('LinkerHand L7')
        self.process_state = label('Process State · Stopped', 'secondary')
        card.body.addWidget(self.process_state)
        self.age = label('', 'secondary')
        card.heading.addWidget(self.age)
        self.summary_values = {}
        summary = QHBoxLayout()
        for key, title in (('state', 'State'), ('communication', 'Communication'), ('input', 'Input')):
            column = QVBoxLayout()
            column.setSpacing(7)
            column.addWidget(label(title, 'secondary'))
            value = label('—', 'value')
            column.addWidget(value)
            self.summary_values[key] = value
            summary.addLayout(column, 1)
        card.body.addLayout(summary)
        card.body.addWidget(divider())
        headings = QHBoxLayout()
        headings.addWidget(label('7 个通道', 'section'))
        headings.addStretch()
        headings.addWidget(label('目标 / 实测 · 0–255', 'secondary'))
        card.body.addLayout(headings)
        self.channel_rows = []
        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.setHorizontalSpacing(36)
        for index, name in enumerate(HAND_CHANNELS):
            grid.addWidget(label(name), index * 2, 0)
            target = label('—', 'secondary', Qt.AlignRight)
            actual = label('—', None, Qt.AlignRight)
            grid.addWidget(target, index * 2, 1)
            grid.addWidget(actual, index * 2, 2)
            bar = progress()
            grid.addWidget(bar, index * 2 + 1, 0, 1, 3)
            self.channel_rows.append((target, actual, bar))
        grid.setColumnStretch(0, 1)
        card.body.addLayout(grid)
        card.body.addSpacing(4)
        self.no_faults = label('', 'secondary')
        self.fault_alert = label('', 'alert')
        self.fault_alert.setWordWrap(True)
        card.body.addWidget(self.no_faults)
        card.body.addWidget(self.fault_alert)
        self.details = Disclosure('触发器与连接详情')
        self.extra = SettingsList()
        for key, title in (('trigger_value', 'Trigger'), ('trigger_pressed', 'Trigger Pressed'),
                           ('trigger_armed', 'Trigger Armed'), ('dry_run', 'Dry Run'),
                           ('connect_only', 'Connect Only'), ('invalid_input_count', 'Invalid Inputs')):
            self.extra.add(key, title)
        self.details.body.addWidget(self.extra)
        card.body.addWidget(self.details)
        self.body.addWidget(card)
        self.body.addWidget(label('Left end-effector integration is not configured.', 'caption'))
        self.body.addStretch(1)

    def update_runtime(self, snapshot):
        external = any(c.key == 'hand' and c.ownership == 'External' for c in snapshot.components)
        self.process_state.setText('Process State · External' if external else
            f'Process State · {snapshot.hand.state.title()} · 独立可选模块')

    def update_snapshot(self, snapshot):
        hand = snapshot.linkerhand
        state = fresh_state(hand.health, hand.state)
        live = hand.health.state == 'ONLINE' and not hand.parse_error
        self.state_label.set_state(state, state.replace('_', ' ').title())
        self.age.setText(age_text(hand.health))
        self.summary_values['state'].setText(hand.hand_toggle_state.title() if live else state)
        self.summary_values['communication'].setText(
            'Online' if live and hand.communication_ok is True else 'Offline'
            if live and hand.communication_ok is False else 'Unknown')
        self.summary_values['input'].setText(
            'Fresh' if live and hand.input_fresh is True else 'Stale'
            if live and hand.input_fresh is False else 'Unknown')
        for index, (target, actual, bar) in enumerate(self.channel_rows):
            target_value = hand.target[index] if hand.target and live else None
            actual_value = hand.actual[index] if hand.actual and live else None
            target.setText(number(target_value, 0))
            actual.setText(number(actual_value, 0))
            value = actual_value if actual_value is not None else target_value
            bar.setValue(round(min(255, value) / 255 * 1000) if value is not None else 0)
            apply_tone(bar, 'blue' if live else 'grey')
        faults = hand.fault_codes if live else None
        fault = bool(faults and any(faults))
        message = hand.parse_error or hand.error
        if fault:
            message = 'Fault codes · ' + ', '.join(str(code) for code in faults) + ('\n' + message if message else '')
        self.fault_alert.setText(message)
        self.fault_alert.setVisible(bool(message))
        apply_tone(self.fault_alert, 'red')
        self.no_faults.setText('No faults detected' if faults is not None and not fault else 'Fault feedback unavailable')
        self.no_faults.setVisible(not message)
        for key in self.extra.fields:
            value = getattr(hand, key) if live else None
            text = ('Yes' if value is True else 'No' if value is False else 'Unknown') if key in (
                'trigger_pressed', 'trigger_armed', 'dry_run', 'connect_only') else number(value, 2 if key == 'trigger_value' else 0)
            self.extra.set_value(key, text)
