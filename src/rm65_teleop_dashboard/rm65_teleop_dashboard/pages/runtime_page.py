"""Runtime management view. Buttons emit intents; the worker owns all processes."""
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QDialog, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from ..preflight import Confirmation, evaluate_preflight
from ..process_manager import LaunchRequest
from ..runtime_dialogs import HardwareConfirmation, ProcessLogDialog, action_button
from ..runtime_observer import TITLES
from ..runtime_service import RuntimeSnapshot
from ..navigation import navigation_icon
from ..widgets import (Card, Page, PrimaryPanel, RuntimeTimeline, SettingsGroup, StyledComboBox,
                       SegmentControl, StatusDot, divider, label, path_text)


STATE_TEXT = {'READY': '就绪', 'WAITING': '等待数据', 'STARTING': '启动中',
              'STOPPED': '未启动', 'STOPPING': '停止中', 'FAILED': '失败',
              'DISABLED': '未启用', 'RUNNING': '运行中'}
STATE_TONE = {'READY': 'READY', 'RUNNING': 'ARMED', 'WAITING': 'HOMING',
              'STARTING': 'HOMING', 'STOPPING': 'HOMING', 'FAILED': 'FAULT'}


class RuntimePage(Page):
    start_requested = pyqtSignal(object, object)
    stop_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__('运行控制', '启动、停止并管理双臂遥操作软件栈')
        self.runtime = RuntimeSnapshot()
        self.confirm_dialog = None
        self.log_dialog = ProcessLogDialog(self)
        self.process_status = StatusDot()
        self.primary = PrimaryPanel()
        top = QHBoxLayout()
        top.setSpacing(32)
        quick = QVBoxLayout()
        quick.setSpacing(12)
        heading = QHBoxLayout()
        heading.addWidget(label('双臂遥操作系统', 'cardTitle'))
        heading.addWidget(self.process_status)
        heading.addStretch()
        quick.addLayout(heading)
        description = label('管理 Quest、双臂驱动、运动控制器和遥操作节点。', 'secondary')
        description.setWordWrap(True)
        quick.addWidget(description)
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.start_button = action_button('启动系统', 'primaryAction')
        self.start_button.setIcon(navigation_icon('play', '#FFFFFF'))
        self.start_button.setIconSize(QSize(16, 16))
        self.dry_button = action_button('Dry Run')
        self.stop_button = action_button('停止系统', 'destructiveAction')
        self.stop_button.setIcon(navigation_icon('stop', '#D70015'))
        self.stop_button.setIconSize(QSize(14, 14))
        for button, width in ((self.start_button, 192), (self.dry_button, 144), (self.stop_button, 144)):
            button.setFixedSize(width, 44)
            buttons.addWidget(button)
        buttons.addStretch()
        quick.addLayout(buttons)
        self.start_button.clicked.connect(lambda: self._start(self.mode.current))
        self.dry_button.clicked.connect(lambda: self._start('dry_run'))
        self.stop_button.clicked.connect(lambda: self.stop_requested.emit('all'))
        note = label('停止软件栈不等于硬件急停；硬件急停由外部设备提供。', 'caption')
        note.setWordWrap(True)
        quick.addWidget(note)
        top.addLayout(quick, 6)
        settings = QVBoxLayout()
        settings.setSpacing(10)
        settings.addWidget(label('启动模式', 'secondary'))
        self.mode = SegmentControl((('dry_run', 'Dry Run'), ('hardware', 'Hardware')))
        self.mode.changed.connect(lambda _: self.update_runtime(self.runtime))
        settings.addWidget(self.mode)
        profile = QHBoxLayout()
        profile.addWidget(label('运动配置', 'secondary'))
        profile.addStretch()
        self.profile = StyledComboBox()
        self.profile.addItems(('Safe', 'Normal'))
        self.profile.setMinimumWidth(110)
        self.profile.setFixedHeight(36)
        profile.addWidget(self.profile)
        settings.addLayout(profile)
        settings.addWidget(label('默认 Dry Run · Safe', 'caption'))
        top.addLayout(settings, 3)
        self.primary.body.addLayout(top)
        self.primary.setMinimumHeight(210)
        self.body.addWidget(self.primary)

        middle = QHBoxLayout()
        middle.setSpacing(16)
        components = Card('组件管理')
        logs = action_button('查看日志')
        logs.setProperty('compactAction', True)
        logs.setFixedSize(84, 32)
        logs.clicked.connect(self.log_dialog.show)
        components.heading.addWidget(logs)
        self.rows = {}
        components.body.setSpacing(0)
        for index, (key, (title, description)) in enumerate(TITLES.items()):
            if index:
                components.body.addWidget(divider())
            container = QWidget()
            container.setMinimumHeight(60)
            row = QHBoxLayout(container)
            row.setContentsMargins(0, 8, 0, 8)
            row.setSpacing(12)
            icon = label('', 'componentIcon')
            icon.setFixedSize(28, 28)
            icon.setAlignment(Qt.AlignCenter)
            icon.setPixmap(navigation_icon({'quest': 'controllers', 'driver': 'arms',
                'control': 'safety', 'adapter': 'runtime-control', 'hand': 'linkerhand'}[key], '#62738A').pixmap(20, 20))
            row.addWidget(icon)
            column = QVBoxLayout()
            column.setSpacing(4)
            column.addWidget(label(title, 'rowTitle'))
            caption = label(description, 'caption')
            caption.setWordWrap(True)
            column.addWidget(caption)
            row.addLayout(column, 5)
            status = StatusDot()
            status.setMinimumWidth(92)
            row.addWidget(status)
            action = action_button('启动') if key == 'hand' else label('由系统管理', 'caption')
            action.setFixedWidth(82)
            action.setEnabled(False)
            if key == 'hand':
                action.setProperty('compactAction', True)
                action.setFixedHeight(32)
                action.clicked.connect(self._hand_action)
            row.addWidget(action)
            components.body.addWidget(container)
            self.rows[key] = (status, action, caption)
        self.ownership = label('外部启动的进程只读显示，不接管、不停止。', 'caption')
        self.ownership.setWordWrap(True)
        components.body.addWidget(self.ownership)
        middle.addWidget(components, 6)

        checks = Card('启动前检查')
        self.check_grid = QGridLayout()
        self.check_grid.setVerticalSpacing(0)
        self.check_grid.setColumnStretch(0, 1)
        self.check_rows = {}
        for index, (key, title) in enumerate((('environment', 'ROS 2 环境'), ('domain', 'ROS Domain'),
            ('graph', 'ROS graph / 进程读取'), ('driver', 'RM Driver'), ('control', 'rm_control'),
            ('tcp', 'TCP 10000'), ('stack', '控制栈'), ('packages', '硬件软件包'),
            ('hand', '灵巧手共存'), ('quest', 'Quest 输入'))):
            name, state = label(title), StatusDot()
            name.setMinimumHeight(36)
            self.check_grid.addWidget(name, index, 0)
            self.check_grid.addWidget(state, index, 1)
            self.check_rows[key] = (name, state)
        checks.body.addLayout(self.check_grid)
        self.check_note = label('硬件模式另需操作者逐项确认。', 'caption')
        self.check_note.setWordWrap(True)
        checks.body.addWidget(self.check_note)
        middle.addWidget(checks, 4)
        self.body.addLayout(middle)
        lower = QHBoxLayout()
        lower.setSpacing(16)
        flow = Card('启动流程')
        self.timeline = RuntimeTimeline((('environment', 'ROS 2 环境'), ('driver', 'RM Driver'),
            ('control', 'RM Control'), ('quest', 'Quest TCP'), ('adapter', 'Teleop Adapter'), ('hand', 'LinkerHand · 可选')))
        self.steps = self.timeline.steps
        flow.body.addWidget(self.timeline)
        lower.addWidget(flow, 6)
        summary = SettingsGroup('运行摘要')
        self.details = summary.settings
        for key, title in (('left_cart', '左臂笛卡尔链路'), ('right_cart', '右臂笛卡尔链路'),
                           ('left_home', '左臂关节轨迹链路'), ('right_home', '右臂关节轨迹链路')):
            self.details.add(key, title)
        self.paths = label('链路状态来自适配器，不代表整个 ROS graph 唯一命令源的安全证明。', 'caption')
        self.paths.setWordWrap(True)
        summary.body.addWidget(self.paths)
        lower.addWidget(summary, 4)
        self.body.addLayout(lower)
        self.error = label('', 'alert')
        self.error.setWordWrap(True)
        self.body.addWidget(self.error)
        self.body.addStretch()
        self.component_card = components
        self.check_card = checks
        self.flow_card = flow
        self.summary_card = summary
        self.update_runtime(self.runtime)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.body.setSpacing(12 if self.compact else 16)
        self.component_card.body.setSpacing(0)
        self.primary.setMinimumHeight(194 if self.compact else 205)
        self.check_card.body.setSpacing(8)
        for card in (self.component_card, self.check_card, self.flow_card, self.summary_card):
            card.body.setContentsMargins(18, 16, 18, 16)
        self.flow_card.body.setSpacing(8)
        self.summary_card.body.setSpacing(8)
        self.details.set_row_height(36)
        for step in self.steps.values():
            step.setFixedHeight(34)
        for button, width in ((self.start_button, 176), (self.dry_button, 130), (self.stop_button, 130)):
            button.setFixedWidth(width if self.compact else {self.start_button: 192,
                self.dry_button: 144, self.stop_button: 144}[button])

    def _start(self, mode, component='system'):
        if not self.runtime.enabled:
            return
        self.mode.select(mode, emit=False)
        request = LaunchRequest(mode, self.profile.currentText().lower(), component)
        preflight = evaluate_preflight(self.runtime.facts, mode, component)
        confirmation = Confirmation()
        if mode == 'hardware':
            self.confirm_dialog = HardwareConfirmation(preflight, self)
            if self.confirm_dialog.exec_() != QDialog.Accepted:
                self.confirm_dialog = None
                return
            confirmation = self.confirm_dialog.confirmation()
            self.confirm_dialog = None
        if preflight.can_start(confirmation):
            self.start_requested.emit(request, confirmation)

    def _hand_action(self):
        if self.runtime.hand.pid is not None:
            self.stop_requested.emit('hand')
        else:
            self._start(self.mode.current, 'hand')

    def update_snapshot(self, snapshot):
        for arm in (snapshot.left, snapshot.right):
            self.details.set_value(arm.side + '_cart', path_text(arm, arm.adapter.command_path_ready))
            self.details.set_value(arm.side + '_home', path_text(arm, arm.adapter.home_command_path_ready))

    def update_runtime(self, snapshot):
        self.runtime = snapshot
        for button in (self.start_button, self.dry_button, self.stop_button, self.rows['hand'][1]):
            if button.property('demoPreview') != snapshot.demo:
                button.setProperty('demoPreview', snapshot.demo)
                button.style().unpolish(button)
                button.style().polish(button)
            button.setToolTip('Demo 模式不会启动真实进程。' if snapshot.demo else '')
        preflight = evaluate_preflight(snapshot.facts, self.mode.current)
        busy = snapshot.system.pid is not None
        self.start_button.setEnabled(snapshot.enabled and not busy and preflight.allowed)
        self.dry_button.setEnabled(snapshot.enabled and not busy and evaluate_preflight(snapshot.facts, 'dry_run').allowed)
        self.stop_button.setEnabled(snapshot.enabled and (busy or snapshot.hand.pid is not None))
        state = snapshot.system.state
        self.process_status.set_state(STATE_TONE.get(state, 'DISABLED'),
            'Demo · 不启动进程' if snapshot.demo else STATE_TEXT.get(state, state))
        for name, state_widget in self.check_rows.values():
            name.hide()
            state_widget.hide()
        for check in preflight.checks:
            if check.key in self.check_rows:
                name, state_widget = self.check_rows[check.key]
                name.show()
                state_widget.show()
                state_widget.set_state({'pass': 'READY', 'warning': 'HOMING', 'blocking': 'FAULT'}[check.level],
                    {'pass': '通过', 'warning': '警告', 'blocking': '阻塞'}[check.level])
                state_widget.setToolTip(check.detail)
                if snapshot.demo:
                    state_widget.set_state('DISABLED', '—  未检查')
                state_widget.dot.setVisible(not snapshot.demo)
        self.check_note.setText('Demo 模式不会启动真实进程。' if snapshot.demo else
                               '检测在启动前重新执行；人工安全条件由操作者确认。')
        self.steps['environment'].set_state('READY' if snapshot.facts.environment_ok else 'DISABLED',
                                           '完成' if snapshot.facts.environment_ok else '未检测')
        for component in snapshot.components:
            state_widget, action, caption = self.rows[component.key]
            text = STATE_TEXT.get(component.state, component.state)
            if component.ownership == 'External':
                text += ' · 外部管理'
            tone = STATE_TONE.get(component.state, 'DISABLED')
            state_widget.set_state(tone, text)
            state_widget.setToolTip(component.detail)
            caption.setText(TITLES[component.key][1])
            self.steps[component.key].set_state(tone, STATE_TEXT.get(component.state, component.state))
            if component.key == 'hand':
                action.setText('停止' if snapshot.hand.pid is not None else '外部管理' if component.ownership == 'External' else '启动')
                action.setEnabled(snapshot.enabled and (snapshot.hand.pid is not None or
                    evaluate_preflight(snapshot.facts, self.mode.current, 'hand').allowed))
            else:
                action.setText('外部管理' if component.ownership == 'External' else '由系统管理')
        pid = snapshot.system.pid
        self.ownership.setText(f'本软件启动组 PID {pid} · 组件跟随现有 dual launch 整体启停。' if pid else
                               '外部启动的进程只读显示，不接管、不停止。')
        message = snapshot.system.error or snapshot.hand.error
        self.error.setText(message)
        self.error.setVisible(bool(message))
        self.log_dialog.update_runtime(snapshot)
        if self.confirm_dialog is not None:
            old = self.confirm_dialog.result
            self.confirm_dialog.update_preflight(evaluate_preflight(snapshot.facts, old.mode, old.component))
