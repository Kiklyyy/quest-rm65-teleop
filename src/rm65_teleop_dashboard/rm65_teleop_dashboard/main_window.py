"""Light desktop shell; navigation never changes the underlying snapshot."""
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget
from .models import SystemSnapshot, operating_mode, summarize_system
from .navigation import Sidebar
from .pages import create_pages
from .styles import stylesheet
from .view_config import PAGES, PAGE_KEYS
from .widgets import StatusDot, label
from .runtime_service import RuntimeSnapshot


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('双臂机器人遥操作监控与运行管理系统 V1.0')
        self.setMinimumSize(1280, 720)
        self.resize(1920, 1080)
        self._compact = False
        self._snapshot = SystemSnapshot()
        self._runtime = RuntimeSnapshot()
        self.setStyleSheet(stylesheet())
        root = QWidget()
        root.setObjectName('DashboardRoot')
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar())
        workspace = QHBoxLayout()
        workspace.setContentsMargins(0, 0, 0, 0)
        workspace.setSpacing(0)
        self.sidebar = Sidebar()
        self.navigation = self.sidebar.navigation
        workspace.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        self.pages = create_pages()
        for page in self.pages.values():
            self.stack.addWidget(page)
        workspace.addWidget(self.stack, 1)
        layout.addLayout(workspace, 1)
        self.navigation.currentRowChanged.connect(self._navigate)
        self.set_page('overview')
        self.update_snapshot(self._snapshot)
        self.update_runtime(self._runtime)

    def _toolbar(self):
        toolbar = QFrame()
        toolbar.setObjectName('Toolbar')
        toolbar.setFixedHeight(62)
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(26, 0, 26, 0)
        row.setSpacing(22)
        self.page_title = label('总览', 'toolbarTitle')
        row.addWidget(self.page_title)
        row.addStretch()
        self.domain_label = label('', 'secondary')
        self.mode_label = label('', 'secondary')
        self.system_label = StatusDot()
        self.ros_label = StatusDot(text='ROS 2')
        self.demo_badge = label('DEMO DATA', 'demo')
        self.readonly_label = label('READ ONLY', 'caption')
        self.readonly_label.setToolTip('只订阅和显示数据；控制与安全由现有系统负责。')
        self.clock = label('', 'secondary')
        for widget in (self.mode_label, self.domain_label, self.ros_label, self.system_label,
                       self.demo_badge, self.readonly_label, self.clock):
            row.addWidget(widget, 0, Qt.AlignVCenter)
        return toolbar

    @property
    def current_page(self):
        return PAGE_KEYS[self.stack.currentIndex()]

    def set_page(self, key):
        if key not in self.pages:
            raise ValueError(f'Unknown dashboard page: {key}')
        self.navigation.setCurrentRow(PAGE_KEYS.index(key))

    def _navigate(self, index):
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        self.page_title.setText(PAGES[index][1])
        self._mode_text()

    def _mode_text(self):
        managed = self.current_page == 'runtime-control' and self._runtime.enabled
        self.readonly_label.setText('CONTROL MODE' if managed else 'READ ONLY')
        self.readonly_label.setToolTip('运行控制页只管理进程；ROS 监测层仍为只读。硬件急停：外部设备。')

    def update_runtime(self, snapshot):
        self._runtime = snapshot
        self._mode_text()
        for page in self.pages.values():
            if hasattr(page, 'update_runtime'):
                page.update_runtime(snapshot)

    def update_snapshot(self, snapshot):
        """Called only by the existing 10 Hz Qt timer."""
        self._snapshot = snapshot
        self.domain_label.setText(f'ROS Domain {snapshot.domain_id}')
        mode = operating_mode(snapshot)
        self.mode_label.setText({'DRY RUN': 'Dry Run', 'HARDWARE': 'Hardware',
                                 'UNKNOWN': 'Mode unknown', 'MIXED': 'Mixed'}.get(mode, mode))
        self.mode_label.setVisible(not snapshot.demo)
        system = summarize_system(snapshot)
        text = {'SYSTEM READY': '系统正常', 'DEGRADED': '需要注意',
                'FAULT': '存在故障', 'OFFLINE': '系统离线'}[system]
        self.system_label.set_state(system, text)
        self.ros_label.set_state('ONLINE' if snapshot.node_count else 'OFFLINE', 'ROS 2')
        self.demo_badge.setVisible(snapshot.demo)
        self.clock.setText(datetime.now().strftime('%H:%M'))
        for page in self.pages.values():
            page.update_snapshot(snapshot)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 1500
        if compact != self._compact:
            self._compact = compact
            self.setStyleSheet(stylesheet(compact))
