"""Runtime management view. Buttons emit intents; the worker owns all processes."""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QDialog, QGridLayout, QHBoxLayout, QVBoxLayout
from ..preflight import Confirmation, evaluate_preflight
from ..process_manager import LaunchRequest
from ..runtime_dialogs import HardwareConfirmation, ProcessLogDialog, action_button
from ..runtime_observer import TITLES
from ..runtime_service import RuntimeSnapshot
from ..widgets import Card, Page, SegmentControl, StatusDot, divider, label, path_text


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
        self.header.addWidget(self.process_status)
        top = QHBoxLayout()
        top.setSpacing(18)
        quick = Card('快速操作')
        quick.body.addWidget(label('复用现有双臂启动配置。启动软件栈不等于机械臂已就绪。', 'secondary'))
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.start_button = action_button('启动系统', 'primaryAction')
        self.dry_button = action_button('Dry Run')
        self.stop_button = action_button('停止系统', 'destructiveAction')
        for button in (self.start_button, self.dry_button, self.stop_button):
            buttons.addWidget(button, 1)
        quick.body.addLayout(buttons)
        self.start_button.clicked.connect(lambda: self._start(self.mode.current))
        self.dry_button.clicked.connect(lambda: self._start('dry_run'))
        self.stop_button.clicked.connect(lambda: self.stop_requested.emit('all'))
        note = label('仅停止本软件启动的进程，不代表硬件急停或已确认机械臂静止。', 'caption')
        note.setWordWrap(True)
        quick.body.addWidget(note)
        top.addWidget(quick, 6)
        settings = Card('启动设置')
        self.mode = SegmentControl((('dry_run', 'Dry Run'), ('hardware', 'Hardware')))
        self.mode.changed.connect(lambda _: self.update_runtime(self.runtime))
        settings.body.addWidget(self.mode)
        profile = QHBoxLayout()
        profile.addWidget(label('Motion Profile', 'secondary'))
        profile.addStretch()
        self.profile = QComboBox()
        self.profile.addItems(('Safe', 'Normal'))
        self.profile.setMinimumWidth(110)
        profile.addWidget(self.profile)
        settings.body.addLayout(profile)
        settings.body.addWidget(label('待应用设置 · 默认 Dry Run / Safe', 'caption'))
        top.addWidget(settings, 3)
        self.body.addLayout(top)

        middle = QHBoxLayout()
        middle.setSpacing(18)
        components = Card('组件管理')
        logs = action_button('查看日志')
        logs.clicked.connect(self.log_dialog.show)
        components.heading.addWidget(logs)
        self.rows = {}
        for index, (key, (title, description)) in enumerate(TITLES.items()):
            if index:
                components.body.addWidget(divider())
            row = QHBoxLayout()
            column = QVBoxLayout()
            column.setSpacing(4)
            column.addWidget(label(title))
            caption = label(description, 'caption')
            caption.setWordWrap(True)
            column.addWidget(caption)
            row.addLayout(column, 5)
            status = StatusDot()
            row.addWidget(status, 2)
            action = action_button('启动' if key == 'hand' else '整栈管理')
            action.setMinimumWidth(84)
            action.setEnabled(False)
            if key == 'hand':
                action.clicked.connect(self._hand_action)
            row.addWidget(action)
            components.body.addLayout(row)
            self.rows[key] = (status, action, caption)
        self.ownership = label('外部启动的进程只读显示，不接管、不停止。', 'caption')
        self.ownership.setWordWrap(True)
        components.body.addWidget(self.ownership)
        middle.addWidget(components, 6)

        right = QVBoxLayout()
        right.setSpacing(18)
        checks = Card('启动前检查')
        self.check_grid = QGridLayout()
        self.check_grid.setVerticalSpacing(10)
        self.check_grid.setColumnStretch(0, 1)
        self.check_rows = {}
        for index, (key, title) in enumerate((('environment', 'ROS 2 环境'), ('domain', 'ROS Domain'),
            ('graph', 'ROS graph / 本机进程'), ('driver', 'RM Driver'), ('control', 'rm_control'),
            ('tcp', 'TCP 10000'), ('stack', '控制栈'), ('packages', '硬件软件包'),
            ('hand', '灵巧手共存'), ('quest', 'Quest 输入'))):
            name, state = label(title, 'secondary'), StatusDot()
            self.check_grid.addWidget(name, index, 0)
            self.check_grid.addWidget(state, index, 1)
            self.check_rows[key] = (name, state)
        checks.body.addLayout(self.check_grid)
        self.check_note = label('硬件模式另需操作者逐项确认。', 'caption')
        self.check_note.setWordWrap(True)
        checks.body.addWidget(self.check_note)
        right.addWidget(checks)
        flow = Card('启动流程')
        self.steps = {}
        step_grid = QGridLayout()
        step_grid.setVerticalSpacing(8)
        for index, (key, title) in enumerate((('environment', 'ROS 2 环境'), ('driver', 'RM Driver'),
            ('control', 'RM Control'), ('quest', 'Quest TCP / 输入'), ('adapter', 'Teleop Adapter'), ('hand', 'LinkerHand'))):
            step_grid.addWidget(label(title, 'secondary'), index, 0)
            self.steps[key] = StatusDot()
            step_grid.addWidget(self.steps[key], index, 1)
        step_grid.setColumnStretch(0, 1)
        flow.body.addLayout(step_grid)
        flow.body.addWidget(label('就绪状态来自节点与实时数据，非 PID。', 'caption'))
        right.addWidget(flow)
        middle.addLayout(right, 4)
        self.body.addLayout(middle)
        self.paths = label('', 'secondary')
        self.paths.setWordWrap(True)
        self.body.addWidget(self.paths)
        self.error = label('', 'alert')
        self.error.setWordWrap(True)
        self.body.addWidget(self.error)
        self.body.addStretch()
        for card in self.findChildren(Card):
            card.body.setContentsMargins(24, 18, 24, 18)
            card.body.setSpacing(12)
        self.check_grid.setVerticalSpacing(6)
        step_grid.setVerticalSpacing(4)
        self.update_runtime(self.runtime)

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
        self.paths.setText('Command path ready  ·  ' + '    /    '.join(
            f'{a.side.title()}：{path_text(a, a.adapter.command_path_ready)}  ·  Home：{path_text(a, a.adapter.home_command_path_ready)}'
            for a in (snapshot.left, snapshot.right)) + '\n路径状态由现有适配器判定，不是整个 ROS graph 唯一命令源的安全证明。')

    def update_runtime(self, snapshot):
        self.runtime = snapshot
        preflight = evaluate_preflight(snapshot.facts, self.mode.current)
        busy = snapshot.system.pid is not None
        self.start_button.setEnabled(snapshot.enabled and not busy and preflight.allowed)
        self.dry_button.setEnabled(snapshot.enabled and not busy and evaluate_preflight(snapshot.facts, 'dry_run').allowed)
        self.stop_button.setEnabled(snapshot.enabled and (busy or snapshot.hand.pid is not None))
        state = snapshot.system.state
        self.process_status.set_state(STATE_TONE.get(state, 'DISABLED'),
            'Demo · 进程操作禁用' if snapshot.demo else '启动组 · ' + STATE_TEXT.get(state, state))
        for name, state_widget in self.check_rows.values():
            name.hide()
            state_widget.hide()
        for check in preflight.checks:
            if check.key in self.check_rows:
                name, state_widget = self.check_rows[check.key]
                name.show()
                state_widget.show()
                state_widget.set_state({'pass': 'READY', 'warning': 'HOMING', 'blocking': 'FAULT'}[check.level],
                    {'pass': '通过', 'warning': '提示', 'blocking': '未通过'}[check.level])
                state_widget.setToolTip(check.detail)
                if snapshot.demo:
                    state_widget.set_state('DISABLED', '未执行')
        self.check_note.setText('Demo 只展示监控数据，启动操作已禁用。' if snapshot.demo else
                               '检测在启动前重新执行；人工安全条件由操作者确认。')
        self.steps['environment'].set_state('READY' if snapshot.facts.environment_ok else 'DISABLED',
                                           '完成' if snapshot.facts.environment_ok else '未检测')
        for component in snapshot.components:
            state_widget, action, caption = self.rows[component.key]
            text = STATE_TEXT.get(component.state, component.state)
            if component.ownership == 'External':
                text += ' · External'
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
                action.setText('外部管理' if component.ownership == 'External' else '整栈管理')
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
