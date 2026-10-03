"""Operator confirmation and bounded plain-text process logs."""
from PyQt5.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QPushButton, QPlainTextEdit, QVBoxLayout
from .preflight import Confirmation
from .widgets import label


def action_button(text, role='secondaryAction'):
    button = QPushButton(text)
    button.setProperty('role', role)
    button.setMinimumHeight(40)
    return button


class HardwareConfirmation(QDialog):
    def __init__(self, preflight, parent=None):
        super().__init__(parent)
        self.setWindowTitle('启动硬件遥操作' if preflight.component == 'system' else '启动右灵巧手硬件')
        self.setMinimumWidth(590)
        self.setModal(True)
        self.result = preflight
        body = QVBoxLayout(self)
        body.setContentsMargins(28, 26, 28, 26)
        body.setSpacing(16)
        body.addWidget(label(self.windowTitle(), 'section'))
        intro = label('启动后，Quest 将具备控制机械臂的能力。\n软件检查不能确认人员位置或硬件急停状态。')
        intro.setWordWrap(True)
        body.addWidget(intro)
        self.check_summary = label('', 'secondary')
        self.check_summary.setWordWrap(True)
        body.addWidget(self.check_summary)
        self.checkboxes = []
        for text in ('工作空间无人', '硬件急停可触及', '操作者已做好机械臂可能响应 Quest 的准备'):
            box = QCheckBox(text)
            box.toggled.connect(self._gate)
            self.checkboxes.append(box)
            body.addWidget(box)
        if preflight.component == 'hand':
            risk = label('右灵巧手会建立第二个 RealMan API 连接。与右 RM65 共存时，\n首次 Grip 可能向旧位姿跳动的现场风险尚未关闭。', 'alert')
            risk.setWordWrap(True)
            body.addWidget(risk)
            box = QCheckBox('了解上述共存风险，并明确授权本次独立启动')
            box.toggled.connect(self._gate)
            self.checkboxes.append(box)
            body.addWidget(box)
        row = QHBoxLayout()
        row.addStretch()
        cancel = action_button('取消')
        cancel.clicked.connect(self.reject)
        self.start_button = action_button('启动', 'primaryAction')
        self.start_button.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(self.start_button)
        body.addLayout(row)
        self.update_preflight(preflight)

    def confirmation(self):
        return Confirmation(*(box.isChecked() for box in self.checkboxes))

    def update_preflight(self, preflight):
        self.result = preflight
        symbols = {'pass': '✓', 'warning': '–', 'blocking': '×'}
        self.check_summary.setText('\n'.join(f'{symbols[c.level]}  {c.title}  ·  {c.detail}' for c in preflight.checks))
        self._gate()

    def _gate(self):
        if hasattr(self, 'start_button'):
            self.start_button.setEnabled(self.result.can_start(self.confirmation()))


class ProcessLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('软件进程日志')
        self.resize(960, 560)
        body = QVBoxLayout(self)
        body.addWidget(label('仅保留每个启动组最近 1000 段输出 · 不采集其他 ROS console', 'secondary'))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(2050)
        body.addWidget(self.output)
        self._last = None

    def update_runtime(self, snapshot):
        value = (snapshot.system_logs, snapshot.hand_logs)
        if value != self._last:
            bar = self.output.verticalScrollBar()
            follow = bar.value() == bar.maximum()
            previous = bar.value()
            self.output.setPlainText('双臂启动组\n' + '\n'.join(value[0]) + '\n\n右灵巧手\n' + '\n'.join(value[1]))
            bar.setValue(bar.maximum() if follow else previous)
            self._last = value
