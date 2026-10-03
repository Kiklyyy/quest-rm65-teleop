"""Existing adapter safety decisions, formatted as settings-style lists."""
from PyQt5.QtWidgets import QHBoxLayout
from ..styles import apply_tone
from ..widgets import (Card, Disclosure, Page, SettingsList, adapter_live,
                       fresh_state, label, number, path_text, progress)


class SafetySection(Card):
    def __init__(self, side):
        super().__init__(side.title() + ' Arm')
        self.settings = SettingsList()
        for key, title in (('state', 'Adapter State'), ('command_path_ready', 'Cartesian Path'),
                           ('home_command_path_ready', 'Home Path'), ('watchdog_count', 'Watchdog'),
                           ('rearm_count', 'Rearm'), ('max_cycle_period_ms', 'Cycle Max'),
                           ('home_action_state', 'Home Action'), ('joint_preset_selection', 'Preset Selection'),
                           ('joint_preset_active', 'Active Preset')):
            self.settings.add(key, title, status=key in ('state', 'command_path_ready', 'home_command_path_ready'))
        self.body.addWidget(self.settings)
        hold = QHBoxLayout()
        hold.addWidget(label('Home Hold', 'secondary'))
        hold.addStretch()
        self.hold_text = label('—', 'secondary')
        hold.addWidget(self.hold_text)
        self.body.addLayout(hold)
        self.hold = progress()
        self.body.addWidget(self.hold)
        self.details = Disclosure('诊断详细信息')
        self.extra = SettingsList()
        self.boolean_fields = (
            ('dry_run', 'Dry Run'), ('hardware_write_enabled', 'Hardware Write'),
            ('hardware_output_available', 'Hardware Output'), ('mapping_verified', 'Mapping Verified'),
            ('deadman_pressed', 'Deadman Pressed'), ('target_fresh', 'Target Fresh'),
            ('quest_pose_fresh', 'Quest Pose Fresh'), ('inputs_fresh', 'Inputs Fresh'),
            ('home_inputs_fresh', 'Home Inputs Fresh'), ('robot_fresh', 'Robot Fresh'),
            ('joint_state_fresh', 'Joint State Fresh'), ('home_button_pressed', 'Home Button'),
            ('joint_presets_enabled', 'Joint Presets Enabled'))
        for key, title in self.boolean_fields:
            self.extra.add(key, title)
        self.extra.add('deadman_source', 'Deadman Source')
        self.age_fields = ('quest_pose_age_ms', 'inputs_age_ms', 'joint_preset_x_inputs_age_ms',
                           'robot_age_ms', 'joint_state_age_ms')
        for key, title in zip(self.age_fields, ('Quest Pose Age', 'Inputs Age', 'Preset X Input Age',
                                               'Robot Age', 'Joint State Age')):
            self.extra.add(key, title)
        self.details.body.addWidget(self.extra)
        self.body.addWidget(self.details)
        self.reason = label('', 'alert')
        self.reason.setWordWrap(True)
        self.body.addWidget(self.reason)

    def update_arm(self, arm):
        status = arm.adapter
        live = adapter_live(arm)
        state = fresh_state(arm.status_health, 'DATA_ERROR' if status.parse_error else status.state)
        self.settings.set_value('state', state)
        for key in ('command_path_ready', 'home_command_path_ready'):
            text = path_text(arm, getattr(status, key))
            self.settings.set_value(key, text, text.upper())
        for key in ('watchdog_count', 'rearm_count', 'max_cycle_period_ms'):
            self.settings.set_value(key, number(getattr(status, key) if live else None,
                                               1 if key == 'max_cycle_period_ms' else 0,
                                               ' ms' if key == 'max_cycle_period_ms' else ''))
        for key in ('home_action_state', 'joint_preset_selection', 'joint_preset_active'):
            value = getattr(status, key)
            self.settings.set_value(key, (value.replace('_', ' ').title() if value else 'Unknown') if live else state)
            self.settings.fields[key].setToolTip(value)
        value = status.home_hold_progress if live else None
        self.hold.setValue(round(value * 1000) if value is not None else 0)
        self.hold_text.setText(number(value * 100 if value is not None else None, 0, '%'))
        for key, _ in self.boolean_fields:
            value = getattr(status, key) if live else None
            self.extra.set_value(key, 'Yes' if value is True else 'No' if value is False else 'Unknown')
        self.extra.set_value('deadman_source', status.deadman_source if live else 'Unknown')
        for key in self.age_fields:
            self.extra.set_value(key, number(getattr(status, key) if live else None, 0, ' ms'))
        reason = status.parse_error or status.reason
        self.reason.setText(reason)
        self.reason.setVisible(bool(reason))
        apply_tone(self.reason, 'red' if status.parse_error or state == 'FAULT' else 'orange')


class SafetyPage(Page):
    def __init__(self):
        super().__init__('安全与控制链路', '观察现有适配器的状态与路径判定')
        row = QHBoxLayout()
        row.setSpacing(22)
        self.sections = {side: SafetySection(side) for side in ('left', 'right')}
        for section in self.sections.values():
            row.addWidget(section, 1)
        self.body.addLayout(row)
        self.process_health = label('', 'secondary')
        self.body.addWidget(self.process_health)
        self.monitor_error = label('', 'alert')
        self.monitor_error.setWordWrap(True)
        self.body.addWidget(self.monitor_error)
        self.body.addWidget(label('监控显示不参与控制判定。硬件急停与机器人安全逻辑由外部系统负责。', 'caption'))
        self.body.addStretch(1)

    def update_runtime(self, snapshot):
        self.process_health.setText(f'Process Health · 启动组 {snapshot.system.state.title()}'
                                   f' · 右灵巧手 {snapshot.hand.state.title()}'
                                   '\n进程状态与上方适配器安全状态分别显示。')

    def update_snapshot(self, snapshot):
        for side, section in self.sections.items():
            section.update_arm(getattr(snapshot, side))
        self.monitor_error.setText(snapshot.monitor_error)
        self.monitor_error.setVisible(bool(snapshot.monitor_error))
        apply_tone(self.monitor_error, 'red')
