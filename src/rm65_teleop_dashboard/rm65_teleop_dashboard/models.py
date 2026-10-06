"""Pure display models. This module never imports ROS or Qt."""
from collections import deque
from dataclasses import dataclass, fields, replace
import json
import math
import threading
import time
from typing import Optional, Tuple


@dataclass(frozen=True)
class StreamHealth:
    state: str = "OFFLINE"
    age_ms: Optional[float] = None
    hz: float = 0.0
    error: str = ""


class FrequencyMeter:
    """Bounded frequency estimation from local monotonic receipt times."""
    def __init__(self, window_s=2.0, max_samples=1024):
        if not finite_number(window_s) or window_s <= 0 or max_samples < 2:
            raise ValueError("positive window and at least two samples required")
        self.window_s = window_s
        self._times = deque(maxlen=max_samples)
        self._last = None
        self._error = ""

    def mark(self, now_s, error=""):
        if not finite_number(now_s) or (self._last is not None and now_s < self._last):
            return
        if self._last != now_s:
            self._times.append(now_s)
        self._last, self._error = now_s, error
        self._prune(now_s)

    def _prune(self, now_s):
        while self._times and now_s - self._times[0] > self.window_s:
            self._times.popleft()

    def health(self, now_s, stale_s=.5, lost_s=2.0):
        if self._last is None:
            return StreamHealth()
        self._prune(now_s)
        age_s = max(0.0, now_s - self._last)
        state = "OFFLINE" if age_s > lost_s else "STALE" if age_s > stale_s else "ONLINE"
        if state == "ONLINE" and self._error:
            state = "INVALID"
        hz = 0.0
        if len(self._times) >= 2 and state in ("ONLINE", "INVALID"):
            duration = self._times[-1] - self._times[0]
            if duration > 0:
                hz = (len(self._times) - 1) / duration
        return StreamHealth(state, age_s * 1000, hz, self._error)


@dataclass(frozen=True)
class AdapterStatus:
    state: str = "UNKNOWN"
    dry_run: Optional[bool] = None
    hardware_write_enabled: Optional[bool] = None
    hardware_output_available: Optional[bool] = None
    mapping_verified: Optional[bool] = None
    deadman_pressed: Optional[bool] = None
    deadman_source: str = ""
    target_fresh: Optional[bool] = None
    quest_pose_fresh: Optional[bool] = None
    inputs_fresh: Optional[bool] = None
    home_inputs_fresh: Optional[bool] = None
    robot_fresh: Optional[bool] = None
    joint_state_fresh: Optional[bool] = None
    quest_pose_age_ms: Optional[float] = None
    inputs_age_ms: Optional[float] = None
    joint_preset_x_inputs_age_ms: Optional[float] = None
    robot_age_ms: Optional[float] = None
    joint_state_age_ms: Optional[float] = None
    rearm_count: Optional[int] = None
    watchdog_count: Optional[int] = None
    home_button_pressed: Optional[bool] = None
    joint_presets_enabled: Optional[bool] = None
    joint_preset_selection: str = ""
    joint_preset_active: str = ""
    home_hold_progress: Optional[float] = None
    home_action_state: str = "UNKNOWN"
    command_path_ready: Optional[bool] = None
    home_command_path_ready: Optional[bool] = None
    max_cycle_period_ms: Optional[float] = None
    reason: str = ""
    parse_error: str = ""


@dataclass(frozen=True)
class LinkerHandSnapshot:
    state: str = "UNKNOWN"
    trigger_value: Optional[float] = None
    trigger_pressed: Optional[bool] = None
    trigger_armed: Optional[bool] = None
    hand_toggle_state: str = "UNKNOWN"
    target: Optional[Tuple[int, ...]] = None
    actual: Optional[Tuple[int, ...]] = None
    fault_codes: Optional[Tuple[int, ...]] = None
    communication_ok: Optional[bool] = None
    input_fresh: Optional[bool] = None
    dry_run: Optional[bool] = None
    connect_only: Optional[bool] = None
    error: str = ""
    invalid_input_count: Optional[int] = None
    parse_error: str = ""
    health: StreamHealth = StreamHealth()


def parse_adapter_status(payload: str) -> AdapterStatus:
    return _parse_status(payload, AdapterStatus)


def parse_linkerhand_status(payload: str) -> LinkerHandSnapshot:
    return _parse_status(payload, LinkerHandSnapshot)


def _parse_status(payload, model_type):
    try:
        decoded = json.loads(payload)
    except (ValueError, TypeError, RecursionError) as exc:
        return model_type(state="DATA_ERROR", parse_error=f"Invalid JSON: {exc}")
    if not isinstance(decoded, dict):
        return model_type(state="DATA_ERROR", parse_error="JSON object required")
    values, errors = {}, []
    for field in fields(model_type):
        if field.name not in decoded or field.name in ("parse_error", "health"):
            continue
        value = decoded[field.name]
        optional = getattr(field.type, "__args__", ())
        expected = optional[0] if optional else field.type
        if value is None and optional:
            values[field.name] = None
            continue
        valid = False
        if expected is bool:
            valid = type(value) is bool
        elif expected is int:
            valid = type(value) is int and value >= 0 and finite_number(value)
        elif expected is float:
            valid = finite_number(value)
            if valid:
                value = float(value)
                if field.name.endswith("_age_ms") and value == -1:
                    value = None  # Adapter's never-received sentinel.
                elif field.name.endswith("_age_ms") or field.name == "max_cycle_period_ms":
                    valid = value >= 0
                elif field.name in ("home_hold_progress", "trigger_value"):
                    valid = 0 <= value <= 1
        elif expected is str:
            valid = isinstance(value, str)
        elif field.name in ("actual", "target", "fault_codes"):
            valid = isinstance(value, list) and len(value) == 7 and all(
                type(item) is int and item >= 0 and finite_number(item) for item in value)
            if valid:
                value = tuple(value)
        if valid:
            values[field.name] = value
        else:
            errors.append(f"{field.name}: invalid value")
    if errors:
        values["parse_error"] = "; ".join(errors)
    return model_type(**values)


JOINT_NAMES = tuple(f"joint{index}" for index in range(1, 7))
HAND_CHANNELS = ("Thumb Pitch", "Thumb Yaw", "Index", "Middle", "Ring", "Little", "Thumb Roll")


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def reorder_joints(names, positions):
    """Return six named joints in degrees plus a visible validation error.

    Unknown extra names are ignored; duplicates and missing values are not
    substituted with zero. The display range is independent of joint limits.
    """
    names, positions = list(names), list(positions)
    result, errors = [], []
    for name in JOINT_NAMES:
        indices = [index for index, item in enumerate(names) if item == name]
        if not indices:
            result.append(None)
            errors.append(f"missing {name}")
        elif len(indices) != 1:
            result.append(None)
            errors.append(f"duplicate {name}")
        elif indices[0] >= len(positions) or not finite_number(positions[indices[0]]):
            result.append(None)
            errors.append(f"invalid {name}")
        else:
            degrees = math.degrees(positions[indices[0]])
            result.append(degrees if finite_number(degrees) else None)
            if not finite_number(degrees):
                errors.append(f"invalid {name}: degree conversion overflow")
    return tuple(result), "; ".join(errors)


def quaternion_to_rpy(x, y, z, w):
    """ROS xyzw quaternion to XYZ roll/pitch/yaw in degrees.

    Quaternion normalization and clamped asin avoid numerical overshoot near
    gimbal lock. Euler angles remain a display representation, not control data.
    """
    values = (x, y, z, w)
    if not all(finite_number(value) for value in values):
        return None
    norm = math.hypot(*values)
    if not math.isfinite(norm) or norm < 1e-12:
        return None
    x, y, z, w = (value / norm for value in values)
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return tuple(math.degrees(value) for value in (roll, pitch, yaw))


@dataclass(frozen=True)
class PoseSnapshot:
    position: Optional[Tuple[float, ...]] = None
    quaternion: Optional[Tuple[float, ...]] = None
    rpy_deg: Optional[Tuple[float, ...]] = None
    error: str = ""


@dataclass(frozen=True)
class ControllerSnapshot:
    pose: PoseSnapshot = PoseSnapshot()
    grip: Optional[float] = None
    trigger: Optional[float] = None
    button_lower: Optional[bool] = None
    button_upper: Optional[bool] = None
    pose_health: StreamHealth = StreamHealth()
    inputs_health: StreamHealth = StreamHealth()


@dataclass(frozen=True)
class ArmSnapshot:
    side: str = ""
    robot_pose: PoseSnapshot = PoseSnapshot()
    target_pose: PoseSnapshot = PoseSnapshot()
    joints_deg: Tuple[Optional[float], ...] = (None,) * 6
    joints_error: str = ""
    adapter: AdapterStatus = AdapterStatus()
    robot_health: StreamHealth = StreamHealth()
    joints_health: StreamHealth = StreamHealth()
    target_health: StreamHealth = StreamHealth()
    status_health: StreamHealth = StreamHealth()


@dataclass(frozen=True)
class EventRecord:
    time_s: float
    level: str
    source: str
    message: str


@dataclass(frozen=True)
class SystemSnapshot:
    left: ArmSnapshot = ArmSnapshot(side="left")
    right: ArmSnapshot = ArmSnapshot(side="right")
    left_controller: ControllerSnapshot = ControllerSnapshot()
    right_controller: ControllerSnapshot = ControllerSnapshot()
    linkerhand: LinkerHandSnapshot = LinkerHandSnapshot()
    demo: bool = False
    domain_id: str = "0"
    node_count: Optional[int] = None
    time_s: float = 0.0
    events: Tuple[EventRecord, ...] = ()
    monitor_error: str = ""


def pose_snapshot(position, quaternion):
    errors = []
    position = tuple(position)
    quaternion = tuple(quaternion)
    if len(position) != 3 or not all(finite_number(value) for value in position):
        errors.append("invalid position")
        position = None
    rpy = quaternion_to_rpy(*quaternion) if len(quaternion) == 4 else None
    if rpy is None:
        errors.append("invalid quaternion")
        quaternion = None
    return PoseSnapshot(position, quaternion, rpy, "; ".join(errors))


def operating_mode(snapshot):
    if snapshot.demo:
        return "DEMO DATA"
    modes = [arm.adapter.dry_run for arm in (snapshot.left, snapshot.right)
             if arm.status_health.state == "ONLINE" and not arm.adapter.parse_error]
    if len(modes) != 2 or any(mode is None for mode in modes):
        return "UNKNOWN"
    if len(modes) == 2 and modes[0] != modes[1]:
        return "MIXED"
    return "DRY RUN" if modes[0] else "HARDWARE"


def status_text(state):
    return state if isinstance(state, str) and state else "UNKNOWN"


def status_color(state):
    return {"green": "#36d5a4", "blue": "#4ea6ee", "orange": "#e8b367",
            "red": "#f27983", "grey": "#8191a3"}[status_tone(state)]


def status_tone(state):
    if state in ("ACTIVE", "READY", "ONLINE", "CONNECTED", "SYSTEM READY", "SUCCEEDED", "PRESSED"):
        return "green"
    if state in ("ARMED", "CONNECT_ONLY", "DRY_RUN", "DRY RUN", "HARDWARE", "OPEN", "CLOSED"):
        return "blue"
    if state in ("HOMING", "REARM_REQUIRED", "STALE", "INPUT_STALE", "DEGRADED", "PENDING", "CANCELING",
                 "BLOCKED", "SERVER_UNAVAILABLE", "DEMO DATA", "MIXED"):
        return "orange"
    if state in ("FAULT", "HAND_FAULT", "COMM_ERROR", "OFFLINE", "LOST", "DATA_ERROR", "INVALID",
                 "ABORTED", "REJECTED"):
        return "red"
    return "grey"


def summarize_system(snapshot):
    if snapshot.monitor_error:
        return "FAULT"
    arms = (snapshot.left, snapshot.right)
    if any(arm.adapter.state == "FAULT" for arm in arms) or snapshot.linkerhand.state in (
            "HAND_FAULT", "COMM_ERROR"):
        return "FAULT"
    core_health = [health for arm in arms for health in (
        arm.robot_health, arm.joints_health, arm.target_health, arm.status_health)] + [
        snapshot.left_controller.pose_health, snapshot.left_controller.inputs_health,
        snapshot.right_controller.pose_health, snapshot.right_controller.inputs_health]
    if all(health.state == "OFFLINE" for health in core_health):
        return "OFFLINE"
    if any(health.state != "ONLINE" for health in core_health):
        return "DEGRADED"
    if any(arm.adapter.parse_error or arm.adapter.state not in (
            "ARMED", "ACTIVE", "HOMING") for arm in arms):
        return "DEGRADED"
    if snapshot.linkerhand.health.state in ("INVALID", "STALE") or (
            snapshot.linkerhand.health.state == "OFFLINE" and
            snapshot.linkerhand.health.age_ms is not None) or (
            snapshot.linkerhand.health.state == "ONLINE" and (
                snapshot.linkerhand.parse_error or snapshot.linkerhand.state not in (
                    "READY", "DRY_RUN", "CONNECT_ONLY"))):
        return "DEGRADED"
    return "SYSTEM READY"


class EventLogger:
    """Bounded GUI-local semantic event history; analog updates are not events."""
    def __init__(self, max_records=500):
        if type(max_records) is not int or max_records < 1 or max_records > 1000:
            raise ValueError("max_records must be 1..1000")
        self._records = deque(maxlen=max_records)
        self._previous = {}

    def update(self, snapshot):
        watched = []
        for side, arm, controller in (("left", snapshot.left, snapshot.left_controller),
                                      ("right", snapshot.right, snapshot.right_controller)):
            source = f"{side}_arm"
            watched.extend([
                (source, "state", arm.adapter.state),
                (source, "reason", arm.adapter.reason),
                (source, "parse_error", arm.adapter.parse_error),
                (source, "home", arm.adapter.home_action_state),
                (source, "watchdog_count", arm.adapter.watchdog_count),
                (source, "cart_path", arm.adapter.command_path_ready),
                (source, "home_path", arm.adapter.home_command_path_ready),
                (source, "joint_preset", arm.adapter.joint_preset_active),
            ])
            for stream, health in (("quest", controller.pose_health),
                                  ("inputs", controller.inputs_health),
                                  ("robot", arm.robot_health),
                                  ("joints", arm.joints_health),
                                  ("status", arm.status_health)):
                watched.append((f"{side}_{stream}", "health", health.state))
        watched.extend([
            ("linkerhand", "state", snapshot.linkerhand.state),
            ("linkerhand", "toggle", snapshot.linkerhand.hand_toggle_state),
            ("linkerhand", "error", snapshot.linkerhand.error or snapshot.linkerhand.parse_error),
            ("system", "monitor_error", snapshot.monitor_error),
        ])
        for source, field, value in watched:
            key = (source, field)
            previous = self._previous.get(key)
            self._previous[key] = value
            if value == previous or value in (None, "", "UNKNOWN"):
                continue
            # Do not fill startup history with absent optional streams.
            if previous is None and value == "OFFLINE":
                continue
            level = "INFO"
            if value in ("FAULT", "COMM_ERROR", "HAND_FAULT", "DATA_ERROR", "INVALID") or (
                    field in ("error", "parse_error", "monitor_error") and value):
                level = "ERROR"
            elif value in ("STALE", "OFFLINE", "INPUT_STALE", "REARM_REQUIRED") or (
                    field in ("cart_path", "home_path") and value is False) or (
                    field == "watchdog_count" and value > (previous or 0)):
                level = "WARN"
            message = str(value) if field in ("state", "toggle", "health") else f"{field}: {value}"
            if field == "reason" and getattr(snapshot, source.split("_")[0]).adapter.state == "FAULT":
                level = "ERROR"
            self._records.append(EventRecord(snapshot.time_s, level, source, message))
        return tuple(self._records)


class SnapshotStore:
    """Callbacks only replace immutable data while holding this lock.

    Qt takes a coherent display copy at its own refresh rate. Receipt time is
    local monotonic time, never a remote ROS header stamp. Timeout values here
    only change display health and do not implement robot safety behavior.
    """
    def __init__(self, domain_id="0"):
        self._lock = threading.Lock()
        self._arms = {side: ArmSnapshot(side=side) for side in ("left", "right")}
        self._controllers = {side: ControllerSnapshot() for side in ("left", "right")}
        self._hand = LinkerHandSnapshot()
        self._meters = {f"{side}.{stream}": FrequencyMeter()
                        for side in ("left", "right")
                        for stream in ("quest", "inputs", "target", "robot", "joints", "status")}
        self._meters["linkerhand"] = FrequencyMeter()
        self._domain_id = str(domain_id)
        self._node_count = None
        self._monitor_error = ""

    def _side(self, side):
        if side not in self._arms:
            raise ValueError(f"unknown arm: {side}")

    def update_pose(self, side, kind, position, quaternion, now_s):
        self._side(side)
        if kind not in ("quest", "target", "robot"):
            raise ValueError(f"unknown pose stream: {kind}")
        pose = pose_snapshot(position, quaternion)
        with self._lock:
            if kind == "quest":
                self._controllers[side] = replace(self._controllers[side], pose=pose)
            else:
                self._arms[side] = replace(self._arms[side], **{f"{kind}_pose": pose})
            self._meters[f"{side}.{kind}"].mark(now_s, pose.error)

    def update_adapter(self, side, payload, now_s):
        self._side(side)
        adapter = parse_adapter_status(payload)
        with self._lock:
            self._arms[side] = replace(self._arms[side], adapter=adapter)
            self._meters[f"{side}.status"].mark(now_s, adapter.parse_error)

    def update_inputs(self, side, grip, trigger, button_lower, button_upper, now_s):
        self._side(side)
        values, errors = {}, []
        for name, value in (("grip", grip), ("trigger", trigger)):
            valid = finite_number(value) and 0 <= value <= 1
            values[name] = float(value) if valid else None
            if not valid:
                errors.append(f"invalid {name}")
        for name, value in (("button_lower", button_lower), ("button_upper", button_upper)):
            values[name] = value if type(value) is bool else None
            if type(value) is not bool:
                errors.append(f"invalid {name}")
        with self._lock:
            self._controllers[side] = replace(self._controllers[side], **values)
            self._meters[f"{side}.inputs"].mark(now_s, "; ".join(errors))

    def update_joints(self, side, names, positions, now_s):
        self._side(side)
        joints, error = reorder_joints(names, positions)
        with self._lock:
            self._arms[side] = replace(self._arms[side], joints_deg=joints, joints_error=error)
            self._meters[f"{side}.joints"].mark(now_s, error)

    def update_linkerhand(self, payload, now_s):
        hand = parse_linkerhand_status(payload)
        with self._lock:
            self._hand = hand
            self._meters["linkerhand"].mark(now_s, hand.parse_error)

    def set_node_count(self, count):
        with self._lock:
            self._node_count = count

    def set_monitor_error(self, error):
        with self._lock:
            self._monitor_error = str(error)

    def snapshot(self, now_s=None):
        now_s = time.monotonic() if now_s is None else now_s
        with self._lock:
            arms, controllers = {}, {}
            for side in ("left", "right"):
                health = {stream: self._meters[f"{side}.{stream}"].health(
                    now_s, stale_s=.1 if stream in ("robot", "joints") else
                    .2 if stream in ("quest", "inputs", "target") else .5)
                          for stream in ("quest", "inputs", "target", "robot", "joints", "status")}
                adapter = self._arms[side].adapter
                if health["status"].state in ("STALE", "OFFLINE"):
                    adapter = AdapterStatus(state=health["status"].state,
                                            reason="Adapter status unavailable")
                elif health["status"].state == "INVALID":
                    adapter = replace(adapter, state="DATA_ERROR")
                arms[side] = replace(self._arms[side], adapter=adapter,
                    robot_health=health["robot"], joints_health=health["joints"],
                    target_health=health["target"], status_health=health["status"])
                controllers[side] = replace(self._controllers[side],
                    pose_health=health["quest"], inputs_health=health["inputs"])
            hand_health = self._meters["linkerhand"].health(now_s)
            hand = replace(self._hand, health=hand_health)
            if hand_health.state in ("STALE", "OFFLINE"):
                hand = LinkerHandSnapshot(state=hand_health.state, health=hand_health)
            elif hand_health.state == "INVALID":
                hand = replace(hand, state="DATA_ERROR")
            return SystemSnapshot(left=arms["left"], right=arms["right"],
                left_controller=controllers["left"], right_controller=controllers["right"],
                linkerhand=hand, domain_id=self._domain_id, node_count=self._node_count,
                time_s=time.time(), monitor_error=self._monitor_error)
