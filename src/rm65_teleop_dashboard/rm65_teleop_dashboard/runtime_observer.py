"""Read-only graph evidence and pure component readiness; no ROS endpoints."""
from dataclasses import dataclass
from pathlib import Path
import socket
from typing import Tuple


NODES = {
    'quest': ('/UnityEndpoint', '/quest_left_target_bridge', '/quest_right_target_bridge'),
    'driver': ('/left/rm_driver', '/right/rm_driver'),
    'control': ('/left/rm_control', '/right/rm_control'),
    'adapter': ('/left_rm65_teleop_adapter', '/rm65_teleop_adapter'),
    'hand': ('/right_linkerhand',),
}
TITLES = {'quest': ('Quest 通信', 'ROS TCP Endpoint · Quest Bridges'),
          'driver': ('机械臂驱动', 'Left / Right RM Driver'),
          'control': ('运动控制器', 'Left / Right rm_control'),
          'adapter': ('遥操作控制', 'Left / Right Teleop Adapter'),
          'hand': ('右灵巧手', 'LinkerHand L7 · 独立可选模块')}


@dataclass(frozen=True)
class GraphEvidence:
    nodes: Tuple[str, ...] = ()
    tcp_listening: bool = False
    graph_ok: bool = True
    processes: Tuple[str, ...] = ()
    process_scan_ok: bool = True
    tcp_port_free: bool = True
    error: str = ''


@dataclass(frozen=True)
class ComponentState:
    key: str
    state: str
    ownership: str = ''
    detail: str = ''


def component_dependencies(mode):
    return {'quest': (), 'driver': (), 'control': ('driver',),
            'adapter': ('quest', 'driver', 'control') if mode == 'hardware' else ('quest',),
            'hand': ()}


def quest_fresh(snapshot):
    return all(h.state == 'ONLINE' for c in (snapshot.left_controller, snapshot.right_controller)
               for h in (c.pose_health, c.inputs_health))


def component_states(graph, snapshot, mode, owned=False, hand_owned=False, hand_mode=None):
    arms = (snapshot.left, snapshot.right)
    live = lambda arm: arm.status_health.state == 'ONLINE' and not arm.adapter.parse_error
    feedback = all(h.state == 'ONLINE' for a in arms for h in (a.robot_health, a.joints_health))
    hand = snapshot.linkerhand
    hand_fresh = hand.health.state == 'ONLINE' and not hand.parse_error
    hand_mode_ok = hand_mode is None or hand.dry_run == (hand_mode == 'dry_run')
    hand_ok = hand_fresh and hand_mode_ok and type(hand.dry_run) is bool
    if hand.dry_run is True:
        hand_ok = hand_ok and hand.state == 'DRY_RUN' and hand.input_fresh is True
    else:
        hand_ok = hand_ok and hand.state in ('READY', 'CONNECT_ONLY')
    if hand.dry_run is False:
        hand_ok = hand_ok and hand.communication_ok is True and (
            hand.input_fresh is True or (hand.state == 'CONNECT_ONLY' and hand.connect_only is True)) and (
            hand.fault_codes is not None and not any(hand.fault_codes))
    evidence = {
        'quest': graph.tcp_listening and quest_fresh(snapshot),
        'driver': feedback,
        'control': all(live(a) and a.adapter.home_command_path_ready is True for a in arms),
        'adapter': all(live(a) for a in arms),
        'hand': hand_ok,
    }
    result = []
    for key, expected in NODES.items():
        counts = [graph.nodes.count(name) for name in expected]
        detected = any(counts)
        managed = hand_owned if key == 'hand' else owned and (mode == 'hardware' or key in ('quest', 'adapter'))
        owner = 'Managed' if managed else 'External' if detected else ''
        if any(n > 1 for n in counts):
            state, detail = 'FAILED', '重复节点：检查其他启动源'
        elif not graph.graph_ok:
            state, detail = 'FAILED', '无法读取 ROS graph'
        elif detected:
            ready = all(n == 1 for n in counts) and evidence[key]
            state, detail = ('READY', '节点与数据已确认') if ready else ('WAITING', '等待节点或实时数据')
            if key == 'hand' and hand_fresh and hand.state in ('COMM_ERROR', 'HAND_FAULT'):
                state, detail = 'FAILED', hand.state
        elif mode == 'dry_run' and key in ('driver', 'control'):
            state, detail = 'DISABLED', 'Dry Run 不启动'
        else:
            state, detail = ('STARTING', '等待 ROS 发现') if owner == 'Managed' else ('STOPPED', '未启动')
        result.append(ComponentState(key, state, owner, detail))
    return tuple(result)


def inspect_graph(node):
    try:
        nodes = tuple(f'{namespace.rstrip("/")}/{name}' for name, namespace in node.get_node_names_and_namespaces())
        graph_ok, error = True, ''
    except Exception as exc:
        nodes, graph_ok, error = (), False, str(exc)
    processes = []
    scan_ok = Path('/proc').is_dir()
    if scan_ok:
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                tokens = (entry / 'cmdline').read_bytes().split(b'\0')
                names = {Path(t.decode(errors='replace')).name for t in tokens if t}
                processes.extend(sorted(names & {'rm_driver', 'rm_control',
                    'rm65_teleop_adapter_node', 'right_linkerhand_node'}))
            except (OSError, ValueError):
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(('0.0.0.0', 10000))
            free = True
        except OSError:
            free = False
    # Read listener state without connecting to the Quest endpoint or sending bytes.
    listening = False
    if scan_ok:
        for filename in ('/proc/net/tcp', '/proc/net/tcp6'):
            try:
                listening |= any(row.split()[1].endswith(':2710') and row.split()[3] == '0A'
                                 for row in Path(filename).read_text().splitlines()[1:])
            except (OSError, IndexError):
                pass
    return GraphEvidence(nodes, listening, graph_ok, tuple(processes), scan_ok, free, error)
