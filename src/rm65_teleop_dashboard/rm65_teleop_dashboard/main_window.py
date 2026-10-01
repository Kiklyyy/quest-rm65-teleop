"""Qt main-thread view of immutable ROS/demo snapshots."""

from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QHeaderView, QMainWindow,
    QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .models import SystemSnapshot, operating_mode, summarize_system
from .styles import COLORS, stylesheet
from .widgets import (
    ArmCard, Card, ControllerCard, LinkerHandCard, OverviewCard,
    RobotOverviewWidget, SafetyCard, age_text, fresh_state, label, number,
    pill, set_state, tone_for,
)


def scroller(widget):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area


def column():
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(9)
    return widget, layout


def combined_health(healths, online="ONLINE"):
    states = [health.state for health in healths]
    if "INVALID" in states:
        return "INVALID"
    if all(state == "OFFLINE" for state in states):
        return "OFFLINE"
    if all(state == "ONLINE" for state in states):
        return online
    return "STALE"


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("双臂机器人遥操作监控系统 · Dual-Arm VR Teleoperation Dashboard")
        self.resize(1920, 1080)
        self.setMinimumSize(1280, 720)
        self._compact = False
        self._events = ()
        self._rendered_events = None
        self._snapshot = SystemSnapshot()
        self.setStyleSheet(stylesheet())
        root = QWidget()
        root.setObjectName("DashboardRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(10)
        layout.addWidget(self._header())
        self.vertical_splitter = QSplitter(Qt.Vertical)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.columns = QSplitter(Qt.Horizontal)
        self.columns.setChildrenCollapsible(False)
        self.columns.addWidget(self._overview())
        self.columns.addWidget(self._core())
        self.columns.addWidget(self._right())
        self.columns.setStretchFactor(0, 18)
        self.columns.setStretchFactor(1, 52)
        self.columns.setStretchFactor(2, 30)
        self.columns.setSizes((330, 980, 565))
        self.vertical_splitter.addWidget(self.columns)
        self.vertical_splitter.addWidget(self._event_log())
        self.vertical_splitter.setStretchFactor(0, 9)
        self.vertical_splitter.setStretchFactor(1, 1)
        self.vertical_splitter.setSizes((820, 145))
        layout.addWidget(self.vertical_splitter, 1)
        footer = QHBoxLayout()
        footer.addWidget(label("RM65 × 2  ·  Quest 6DoF  ·  ROS 2 Humble", "secondary"))
        footer.addStretch()
        footer.addWidget(label("只读订阅监控  /  No motion authority", "secondary"))
        layout.addLayout(footer)
        self.update_snapshot(self._snapshot)

    def _header(self):
        card = QFrame()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(5, 0, 5, 4)
        layout.setSpacing(15)
        title_column = QVBoxLayout()
        title_column.setSpacing(4)
        title_column.addWidget(label("双臂机器人遥操作监控系统", "title"))
        title_column.addWidget(label("ROS 2  ·  VR Teleoperation  ·  Dual RM65", "secondary"))
        layout.addLayout(title_column)
        layout.addStretch()
        self.domain_label = label("DOMAIN  —", "eyebrow")
        layout.addWidget(self.domain_label)
        self.mode_label = pill("UNKNOWN")
        layout.addWidget(self.mode_label)
        self.system_label = pill("OFFLINE")
        layout.addWidget(self.system_label)
        self.demo_badge = pill("DEMO DATA")
        layout.addWidget(self.demo_badge)
        self.clock = label("", "numeric")
        layout.addWidget(self.clock)
        readonly = pill("监控模式 / READ ONLY")
        readonly.setToolTip("This application only observes ROS data. Robot safety is managed by the existing adapter and external hardware.")
        layout.addWidget(readonly)
        self.monitor_error = label("", "secondary")
        self.monitor_error.setWordWrap(True)
        title_column.addWidget(self.monitor_error)
        return card

    def _overview(self):
        content, layout = column()
        layout.addWidget(label("SYSTEM OVERVIEW  /  系统概览", "eyebrow"))
        self.quest_card = OverviewCard("Quest / ROS TCP")
        self.ros_card = OverviewCard("ROS 2")
        self.left_card = OverviewCard("Left RM65")
        self.right_card = OverviewCard("Right RM65")
        self.hand_card = OverviewCard("Right LinkerHand")
        self.safety_overview = OverviewCard("Safety")
        for card in (self.quest_card, self.ros_card, self.left_card, self.right_card, self.hand_card, self.safety_overview):
            layout.addWidget(card)
        mapping = Card("Control Mapping", "Existing controller bindings · display only")
        mapping.body.addWidget(label("LEFT", "eyebrow"))
        mapping.body.addWidget(label("Grip → Cartesian Teleop\nX → Right Preset 1\nY → Left Home", "secondary"))
        mapping.body.addSpacing(3)
        mapping.body.addWidget(label("RIGHT", "eyebrow"))
        mapping.body.addWidget(label("Grip → Cartesian Teleop\nIndex → LinkerHand Toggle\nA → Right Preset 2\nB → Right Preset 3", "secondary"))
        layout.addWidget(mapping)
        layout.addStretch()
        area = scroller(content)
        area.setMinimumWidth(200)
        return area

    def _core(self):
        core = Card("Dual-Arm Teleoperation  /  双臂遥操作状态", role="panel")
        core.heading.addWidget(label("TCP & JOINT FEEDBACK", "eyebrow"))
        arms = QHBoxLayout()
        arms.setSpacing(10)
        self.left_arm = ArmCard("left")
        self.right_arm = ArmCard("right")
        center, center_layout = column()
        center_layout.addWidget(label("ROBOT OVERVIEW", "eyebrow", Qt.AlignCenter))
        self.robot = RobotOverviewWidget()
        center_layout.addWidget(self.robot, 1)
        center_layout.addWidget(label("双 RM65 · 每臂 6 个关节", "secondary", Qt.AlignCenter))
        center_layout.addWidget(label("状态示意 · 非实时运动学模型", "secondary", Qt.AlignCenter))
        arms.addWidget(self.left_arm, 4)
        arms.addWidget(center, 3)
        arms.addWidget(self.right_arm, 4)
        arms_container = QWidget()
        arms_container.setLayout(arms)
        core.body.addWidget(scroller(arms_container), 1)
        self.target_label = label("BRIDGE TARGETS   LEFT —   RIGHT —", "secondary")
        self.target_label.setWordWrap(True)
        self.target_label.setToolTip("Read-only Quest bridge targets, not robot commands. Orientation in the existing target bridge is only a placeholder.")
        core.body.addWidget(self.target_label)
        core.setMinimumWidth(600)
        return core

    def _right(self):
        content, layout = column()
        controllers = Card("VR Controller Inputs", role="panel")
        controllers.body.setContentsMargins(12, 8, 12, 8)
        controllers.body.setSpacing(5)
        controllers.heading.addWidget(label("QUEST · LIVE INPUT", "eyebrow"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.left_controller = ControllerCard("left")
        self.right_controller = ControllerCard("right")
        row.addWidget(self.left_controller, 1)
        row.addWidget(self.right_controller, 1)
        controllers.body.addLayout(row)
        layout.addWidget(controllers)
        self.safety_card = SafetyCard()
        layout.addWidget(self.safety_card)
        self.linkerhand_card = LinkerHandCard()
        layout.addWidget(self.linkerhand_card)
        layout.addStretch()
        area = scroller(content)
        area.setMinimumWidth(375)
        return area

    def _event_log(self):
        card = Card("Event Log  /  事件日志", role="panel")
        card.body.setContentsMargins(12, 6, 12, 6)
        card.body.setSpacing(4)
        card.heading.addWidget(label("LOCAL STATE CHANGES · MAX 500", "eyebrow"))
        self.log_filter = QComboBox()
        self.log_filter.setFixedHeight(24)
        self.log_filter.addItems(("All", "Info", "Warning", "Error"))
        self.log_filter.currentTextChanged.connect(self._filter_events)
        card.heading.addWidget(self.log_filter)
        self.events_table = QTableWidget(0, 4)
        self.events_table.setHorizontalHeaderLabels(("TIME", "LEVEL", "SOURCE", "MESSAGE"))
        self.events_table.verticalHeader().hide()
        self.events_table.verticalHeader().setDefaultSectionSize(20)
        self.events_table.setShowGrid(False)
        self.events_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.events_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.events_table.horizontalHeader()
        header.setFixedHeight(24)
        for i in range(3):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        card.body.addWidget(self.events_table)
        card.setMinimumHeight(125)
        return card

    def _filter_events(self, _text=None):
        choice = self.log_filter.currentText()
        allowed = {"Info": "INFO", "Warning": "WARN", "Error": "ERROR"}.get(choice)
        events = tuple(event for event in self._events[-500:] if allowed is None or event.level == allowed)
        if events == self._rendered_events:
            return
        self._rendered_events = events
        self.events_table.setUpdatesEnabled(False)
        self.events_table.setRowCount(len(events))
        for row, event in enumerate(events):
            timestamp = datetime.fromtimestamp(event.time_s).strftime("%H:%M:%S")
            for column, text in enumerate((timestamp, event.level, event.source, event.message)):
                item = QTableWidgetItem(text)
                if column == 1:
                    item.setForeground(QColor(COLORS["red" if event.level == "ERROR" else "orange" if event.level == "WARN" else "blue"]))
                self.events_table.setItem(row, column, item)
        self.events_table.scrollToBottom()
        QTimer.singleShot(0, self.events_table.scrollToBottom)
        self.events_table.setUpdatesEnabled(True)

    def update_snapshot(self, snapshot):
        """Called at 10 Hz by the Qt timer, never from a ROS callback."""
        self._snapshot = snapshot
        self.domain_label.setText(f"DOMAIN  {snapshot.domain_id}")
        set_state(self.mode_label, operating_mode(snapshot))
        self.mode_label.setVisible(not snapshot.demo)
        set_state(self.system_label, summarize_system(snapshot))
        self.demo_badge.setVisible(snapshot.demo)
        self.clock.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.monitor_error.setText(snapshot.monitor_error)
        self.monitor_error.setVisible(bool(snapshot.monitor_error))
        if snapshot.monitor_error:
            set_state(self.monitor_error, "MONITOR ERROR: " + snapshot.monitor_error, "red")
        self.left_arm.update_arm(snapshot.left, snapshot.left_controller)
        self.right_arm.update_arm(snapshot.right, snapshot.right_controller)
        self.robot.update_states(fresh_state(snapshot.left.status_health, snapshot.left.adapter.state),
                                 fresh_state(snapshot.right.status_health, snapshot.right.adapter.state))
        self.left_controller.update_controller(snapshot.left_controller)
        self.right_controller.update_controller(snapshot.right_controller)
        self.safety_card.update_arms(snapshot.left, snapshot.right)
        self.linkerhand_card.update_hand(snapshot.linkerhand)
        self._update_overview(snapshot)
        def target_text(arm):
            position = " / ".join(number(v, 3) for v in (arm.target_pose.position or (None,) * 3))
            return f"{arm.side.upper()}  {position} m  [{arm.target_health.state}]"
        self.target_label.setText("BRIDGE TARGETS   " + target_text(snapshot.left) + "    ·    " + target_text(snapshot.right))
        self._events = snapshot.events
        self._filter_events()

    def _update_overview(self, snapshot):
        left, right = snapshot.left_controller, snapshot.right_controller
        quest_state = combined_health((left.pose_health, left.inputs_health, right.pose_health, right.inputs_health))
        self.quest_card.update_value(quest_state,
            f"Left  {combined_health((left.pose_health, left.inputs_health))}  ·  {number(left.pose_health.hz, 1)} Hz  ·  {age_text(left.pose_health)}\n"
            f"Right  {combined_health((right.pose_health, right.inputs_health))}  ·  {number(right.pose_health.hz, 1)} Hz  ·  {age_text(right.pose_health)}")
        ros_state = "DEMO DATA" if snapshot.demo else "DEGRADED" if snapshot.monitor_error else "CONNECTED" if snapshot.node_count is not None else "UNKNOWN"
        self.ros_card.update_value(ros_state, f"Domain ID  {snapshot.domain_id}\nDiscovered nodes  {number(snapshot.node_count, 0)}")
        for arm, card in ((snapshot.left, self.left_card), (snapshot.right, self.right_card)):
            health = combined_health((arm.robot_health, arm.joints_health, arm.status_health), "CONNECTED")
            card.update_value(health, f"TCP  {number(arm.robot_health.hz, 1)} Hz  ·  {age_text(arm.robot_health)}\nJoints  {number(arm.joints_health.hz, 1)} Hz  ·  {age_text(arm.joints_health)}")
        hand = snapshot.linkerhand
        state = fresh_state(hand.health, hand.state)
        self.hand_card.update_value(state, f"{hand.hand_toggle_state}  ·  {age_text(hand.health)}\n7 hand channels · right side only")
        fault = any(arm.adapter.state == "FAULT" for arm in (snapshot.left, snapshot.right))
        safety_state = "FAULT" if fault else "DEGRADED" if any(arm.status_health.state != "ONLINE" for arm in (snapshot.left, snapshot.right)) else "READY"
        self.safety_overview.update_value(safety_state,
            f"Watchdog L / R   {number(snapshot.left.adapter.watchdog_count, 0)} / {number(snapshot.right.adapter.watchdog_count, 0)}\n"
            f"Fault observed   {'YES' if fault else 'NO' if safety_state == 'READY' else 'UNKNOWN'}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 1500
        if compact != self._compact:
            self._compact = compact
            self.setStyleSheet(stylesheet(compact))
            if hasattr(self, "left_controller"):
                self.left_controller.glyph.setVisible(not compact)
                self.right_controller.glyph.setVisible(not compact)
                self.left_arm.set_compact(compact)
                self.right_arm.set_compact(compact)
