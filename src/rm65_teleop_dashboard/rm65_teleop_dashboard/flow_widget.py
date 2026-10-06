"""Read-only presentation of telemetry and lifecycle snapshots, with no ROS dependency."""
from dataclasses import dataclass
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget
from .widgets import combined_health, fresh_state


@dataclass(frozen=True)
class FlowNode:
    key: str
    title: str
    state: str
    detail: str
    optional: bool = False
    external: bool = False


def overview_nodes(snapshot):
    nodes = []
    for side in ('left', 'right'):
        controller = getattr(snapshot, side + '_controller')
        state = combined_health((controller.pose_health, controller.inputs_health))
        nodes.append(FlowNode('quest_' + side, 'Quest ' + side[0].upper(), state,
                              'Online' if state == 'ONLINE' else state))
    ros = 'FAULT' if snapshot.monitor_error else 'READY' if snapshot.node_count else 'OFFLINE'
    nodes.append(FlowNode('ros', 'ROS 2', ros, 'Graph online' if ros == 'READY' else ros))
    states = [fresh_state(a.status_health, 'DATA_ERROR' if a.adapter.parse_error else a.adapter.state)
              for a in (snapshot.left, snapshot.right)]
    teleop = adapter_summary(states)
    nodes.append(FlowNode('teleop', 'Teleop', teleop, '适配器在线' if teleop == 'READY' else teleop))
    for arm in (snapshot.left, snapshot.right):
        health = combined_health((arm.status_health, arm.robot_health, arm.joints_health))
        live_state = fresh_state(arm.status_health, 'DATA_ERROR' if arm.adapter.parse_error else arm.adapter.state)
        state = live_state if live_state in ('FAULT', 'DATA_ERROR') or health == 'ONLINE' else health
        nodes.append(FlowNode(arm.side, arm.side.title() + ' RM65', state, state))
    hand = snapshot.linkerhand
    state = fresh_state(hand.health, 'DATA_ERROR' if hand.parse_error else hand.state)
    detail = state + ' · ' + hand.hand_toggle_state if state == 'READY' and hand.hand_toggle_state else state
    if state in ('OFFLINE', 'LOST'):
        detail = '可选 · Offline' if hand.health.age_ms is None else '可选 · LOST'
    nodes.append(FlowNode('hand', 'Right Hand', state, detail, optional=True))
    return {node.key: node for node in nodes}


def adapter_summary(states):
    """Summarize already-reported states for a label, not a control decision."""
    for state in ('FAULT', 'DATA_ERROR', 'INVALID'):
        if state in states:
            return state
    if all(s in ('LOST', 'OFFLINE') for s in states):
        return 'OFFLINE'
    if any(s in ('LOST', 'OFFLINE', 'STALE') for s in states):
        return 'STALE'
    for state in ('REARM_REQUIRED', 'HOMING'):
        if state in states:
            return state
    if all(s in ('ACTIVE', 'ARMED') for s in states):
        return 'READY'
    return 'DISABLED' if all(s == 'DISABLED' for s in states) else 'WAITING'


def node_color(node):
    if node.state in ('FAULT', 'FAILED', 'INVALID', 'DATA_ERROR', 'COMM_ERROR', 'HAND_FAULT'):
        return '#FF3B30'
    if node.state in ('STALE', 'INPUT_STALE', 'REARM_REQUIRED', 'HOMING', 'WAITING', 'STOPPING'):
        return '#FF9F0A'
    if node.external and node.state in ('ACTIVE', 'READY', 'RUNNING', 'ONLINE', 'ARMED',
                                        'STARTING', 'CONNECT_ONLY', 'DRY_RUN'):
        return '#829AB5'
    if node.state in ('ACTIVE', 'READY', 'RUNNING', 'ONLINE'):
        return '#34C759'
    if node.state in ('ARMED', 'STARTING', 'CONNECT_ONLY', 'DRY_RUN'):
        return '#007AFF'
    return '#FF3B30' if node.state in ('OFFLINE', 'LOST') and not node.optional else '#8E8E93'


RUNTIME_TEXT = {'READY': '已就绪', 'RUNNING': '运行中', 'STARTING': '正在启动',
                'STOPPED': '未启动', 'STOPPING': '正在停止', 'FAILED': '失败',
                'WAITING': '等待数据', 'DISABLED': '未启用'}


def runtime_nodes(snapshot):
    environment = snapshot.facts.environment_ok
    nodes = [FlowNode('environment', 'ROS 2', 'READY' if environment else 'STOPPED',
                      '环境已加载' if environment else '未检测')]
    components = {c.key: c for c in snapshot.components}
    for key, title in (('driver', 'RM Driver'), ('control', 'RM Control'),
                       ('quest', 'Quest TCP'), ('adapter', 'Teleop Adapter'), ('hand', 'LinkerHand')):
        component = components.get(key)
        state = component.state if component else 'STOPPED'
        external = bool(component and component.ownership == 'External')
        detail = ('外部管理 · ' if external else '可选 · ' if key == 'hand' else '') + RUNTIME_TEXT.get(state, state)
        nodes.append(FlowNode(key, title, state, detail, optional=key == 'hand', external=external))
    return {n.key: n for n in nodes}


def link_color(source, target, active=False):
    if any(n.state in ('FAULT', 'FAILED', 'INVALID', 'DATA_ERROR', 'COMM_ERROR', 'HAND_FAULT')
           for n in (source, target)):
        return '#FF3B30'
    if any(n.state in ('OFFLINE', 'LOST', 'STOPPED', 'DISABLED', 'UNKNOWN') for n in (source, target)):
        return '#D1D1D6'
    if any(n.state in ('STALE', 'INPUT_STALE', 'REARM_REQUIRED', 'HOMING', 'WAITING', 'STOPPING')
           for n in (source, target)):
        return '#FF9F0A'
    if not all(n.state in ('READY', 'ACTIVE', 'ARMED', 'ONLINE', 'RUNNING', 'STARTING',
                          'CONNECT_ONLY', 'DRY_RUN') for n in (source, target)):
        return '#D1D1D6'
    return '#007AFF' if active else '#9CC7F7'


class TeleopFlowWidget(QWidget):
    """Two explicitly different diagrams; paint only when existing state changes."""
    def __init__(self, kind='overview', parent=None):
        super().__init__(parent)
        self.kind = kind
        self.nodes = {}
        self.active_sides = set()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(112 if kind == 'overview' else 56)
        self.setToolTip('状态连线仅显示现有数据与软件状态，不代表安全认证或唯一命令源。')

    def set_snapshot(self, snapshot):
        self.nodes = overview_nodes(snapshot)
        self.active_sides = {a.side for a in (snapshot.left, snapshot.right)
                             if self.nodes[a.side].state == 'ACTIVE'
                             and a.adapter.command_path_ready is True
                             and self.nodes['quest_' + a.side].state == 'ONLINE'
                             and a.target_health.state == 'ONLINE'}
        self._refresh()

    def _refresh(self):
        self.setAccessibleName('遥操作数据链路' if self.kind == 'overview' else '软件栈状态流')
        self.setAccessibleDescription('; '.join(n.title + ': ' + n.detail for n in self.nodes.values()))
        self.update()

    def set_runtime(self, snapshot):
        self.nodes = runtime_nodes(snapshot)
        self.active_sides = set()
        self._refresh()

    def node_rects(self):
        width = min(138, self.width() / 6.6)
        span = max(0, self.width() - width)
        if self.kind == 'runtime':
            font = QFont(self.font())
            font.setPixelSize(13)
            font.setWeight(QFont.Medium)
            metrics = QFontMetrics(font)
            widths = {key: max(74, metrics.horizontalAdvance(node.title) + 24)
                      for key, node in self.nodes.items()}
            gap = max(0, (self.width() - sum(widths.values())) / max(1, len(widths) - 1))
            rects, x = {}, 0
            for key, node_width in widths.items():
                rects[key] = QRectF(x, 12, node_width, 38)
                x += node_width + gap
            return rects
        top, bottom = 3, self.height() - 40
        center = (top + bottom) / 2
        return {key: QRectF(span * x, y, width, 38) for key, x, y in (
            ('quest_left', 0, top), ('quest_right', 0, bottom), ('ros', .24, center),
            ('teleop', .47, center), ('left', .72, top), ('right', .72, bottom), ('hand', 1, bottom))}

    def paintEvent(self, event):
        if not self.nodes:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rects = self.node_rects()
        pairs = (list(zip(self.nodes, list(self.nodes)[1:])) if self.kind == 'runtime' else
                 [('quest_left', 'ros'), ('quest_right', 'ros'), ('ros', 'teleop'),
                  ('teleop', 'left'), ('teleop', 'right'), ('right', 'hand')])
        for source, target in pairs:
            a, b = rects[source], rects[target]
            active = (target in self.active_sides or source == 'quest_left' and 'left' in self.active_sides
                      or source == 'quest_right' and 'right' in self.active_sides
                      or (source, target) == ('ros', 'teleop') and bool(self.active_sides))
            color = link_color(self.nodes[source], self.nodes[target], active)
            painter.setPen(QPen(QColor(color), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            start, end = QPointF(a.right() + 5, a.top() + 10), QPointF(b.left() - 10, b.top() + 10)
            path = QPainterPath(start)
            mid = (start.x() + end.x()) / 2
            path.cubicTo(QPointF(mid, start.y()), QPointF(mid, end.y()), end)
            painter.drawPath(path)
        for key, node in self.nodes.items():
            rect = rects[key]
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(node_color(node)))
            painter.drawEllipse(QPointF(rect.left() + 5, rect.top() + 10), 4, 4)
            font = QFont(self.font())
            font.setPixelSize(13)
            font.setWeight(QFont.Medium)
            painter.setFont(font)
            painter.setPen(QColor('#1D1D1F'))
            painter.drawText(QRectF(rect.left() + 20, rect.top() - 2, rect.width() - 20, 24),
                             Qt.AlignLeft | Qt.AlignVCenter, node.title)
            font.setPixelSize(11)
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor('#8E8E93'))
            text = painter.fontMetrics().elidedText(node.detail, Qt.ElideRight, int(rect.width() - 20))
            painter.drawText(QRectF(rect.left() + 20, rect.top() + 20, rect.width() - 20, 18),
                             Qt.AlignLeft | Qt.AlignVCenter, text)
