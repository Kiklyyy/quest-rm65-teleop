"""Runtime management view. Buttons emit intents; the worker owns all processes."""
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from ..preflight import Confirmation, evaluate_preflight
from ..process_manager import LaunchRequest
from ..runtime_dialogs import HardwareConfirmation, ProcessLogDialog, action_button
from ..runtime_observer import TITLES
from ..runtime_service import RuntimeSnapshot
from ..navigation import navigation_icon
from ..flow_widget import TeleopFlowWidget
from ..widgets import (Card, Page, PrimaryPanel, SettingsGroup, StyledComboBox,
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
        top = QHBoxLayout()
        top.setSpacing(16)
        self.primary = PrimaryPanel()
        heading = QHBoxLayout()
        heading.addWidget(label('双臂遥操作系统', 'cardTitle'))
        heading.addStretch()
        heading.addWidget(self.process_status)
        self.primary.body.addLayout(heading)
        description = label('管理 Quest、双臂驱动、运动控制器和遥操作节点。', 'secondary')
        description.setWordWrap(True)
        self.primary.body.addWidget(description)
        self.primary.body.addStretch()
        self.flow = TeleopFlowWidget('runtime')
        self.primary.body.addWidget(self.flow)
        self.primary.body.addStretch()
        self.flow_caption = label('', 'caption')
        self.primary.body.addWidget(self.flow_caption)
        top.addWidget(self.primary, 7)

        self.settings_panel = Card('启动设置')
        settings = self.settings_panel.body
        mode_group = QVBoxLayout()
        mode_group.setSpacing(4)
        mode_group.addWidget(label('运行模式', 'secondary'))
        self.mode = SegmentControl((('dry_run', 'Dry Run'), ('hardware', 'Hardware')))
        self.mode.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mode.changed.connect(lambda _: self.update_runtime(self.runtime))
        mode_group.addWidget(self.mode)
        settings.addLayout(mode_group)
        profile_group = QVBoxLayout()
        profile_group.setSpacing(4)
        profile_group.addWidget(label('运动配置', 'secondary'))
        self.profile = StyledComboBox()
        self.profile.addItems(('Safe', 'Normal'))
        self.profile.setFixedHeight(36)
        profile_group.addWidget(self.profile)
        settings.addLayout(profile_group)
        self.start_button = action_button('启动系统', 'primaryAction')
        self.start_button.setIcon(navigation_icon('play', '#FFFFFF'))
        self.start_button.setIconSize(QSize(16, 16))
        self.stop_button = action_button('停止系统', 'destructiveAction')
        self.stop_button.setIcon(navigation_icon('stop', '#D70015'))
        self.stop_button.setIconSize(QSize(14, 14))
        self.start_button.setFixedHeight(44)
        self.stop_button.setFixedHeight(40)
        settings.addWidget(self.start_button)
        settings.addWidget(self.stop_button)
        self.start_button.clicked.connect(lambda: self._start(self.mode.current))
        self.stop_button.clicked.connect(lambda: self.stop_requested.emit('all'))
        note = label('停止系统仅停止本软件管理的进程。\n硬件急停由外部设备提供。', 'caption')
        note.setWordWrap(True)
        settings.addWidget(note)
        top.addWidget(self.settings_panel, 3)
        self.body.addLayout(top)

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
        runtime_info = SettingsGroup('运行状态')
        self.runtime_details = runtime_info.settings
        for key, title in (('phase', '软件栈阶段'), ('owner', '软件栈归属'),
                           ('pid', '软件栈进程组 PID'), ('exit', '软件栈退出码')):
            self.runtime_details.add(key, title)
        lower.addWidget(runtime_info, 6)
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
        self.flow_card = runtime_info
        self.summary_card = summary
        self.update_runtime(self.runtime)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.body.setSpacing(12 if self.compact else 16)
        self.component_card.body.setSpacing(0)
        self.primary.body.setSpacing(12)
        self.primary.body.setContentsMargins(18 if self.compact else 24, 16,
                                            18 if self.compact else 24, 16)
        self.settings_panel.body.setContentsMargins(18, 16, 18, 16)
        self.settings_panel.body.setSpacing(10)
        self.check_card.body.setSpacing(8)
        for card in (self.component_card, self.check_card, self.flow_card, self.summary_card):
            card.body.setContentsMargins(18, 16, 18, 16)
        self.flow_card.body.setSpacing(8)
        self.summary_card.body.setSpacing(8)
        self.details.set_row_height(36)
        self.runtime_details.set_row_height(36)

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
        for button in (self.start_button, self.stop_button, self.rows['hand'][1]):
            if button.property('demoPreview') != snapshot.demo:
                button.setProperty('demoPreview', snapshot.demo)
                button.style().unpolish(button)
                button.style().polish(button)
            button.setToolTip('Demo 模式不会启动真实进程。' if snapshot.demo else '')
        preflight = evaluate_preflight(snapshot.facts, self.mode.current)
        busy = snapshot.system.pid is not None
        self.start_button.setEnabled(snapshot.enabled and not busy and preflight.allowed)
        self.stop_button.setEnabled(snapshot.enabled and (busy or snapshot.hand.pid is not None))
        state = snapshot.system.state
        text = {'STOPPED': '未运行', 'STARTING': '正在启动', 'RUNNING': '运行中 · 等待就绪',
                'STOPPING': '正在停止', 'FAILED': '启动失败'}.get(state, state)
        if state == 'RUNNING' and snapshot.ready:
            text = '已就绪'
        self.process_status.set_state(STATE_TONE.get(state, 'DISABLED'),
            '未运行' if snapshot.demo else text)
        self.flow_caption.setText('Demo 模式不会启动真实进程' if snapshot.demo else
            '软件栈尚未启动' if state == 'STOPPED' else '组件状态根据现有 ROS 就绪证据更新')
        self.flow.set_runtime(snapshot)
        self.runtime_details.set_value('phase', 'Demo · 不启动进程' if snapshot.demo else text)
        external = any(c.ownership == 'External' and c.key != 'hand' for c in snapshot.components)
        self.runtime_details.set_value('owner', '本软件管理' if busy else '外部管理' if external else '—')
        self.runtime_details.set_value('pid', str(snapshot.system.pid) if busy else '—')
        self.runtime_details.set_value('exit', str(snapshot.system.exit_code) if snapshot.system.exit_code is not None else '—')
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
        for component in snapshot.components:
            state_widget, action, caption = self.rows[component.key]
            text = STATE_TEXT.get(component.state, component.state)
            if component.ownership == 'External':
                text += ' · 外部管理'
            tone = STATE_TONE.get(component.state, 'DISABLED')
            state_widget.set_state(tone, text)
            state_widget.setToolTip(component.detail)
            caption.setText(TITLES[component.key][1])
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
