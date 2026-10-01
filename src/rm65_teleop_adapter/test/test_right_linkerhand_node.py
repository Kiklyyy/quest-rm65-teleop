"""Isolated ROS tests using synthetic Quest Inputs and an in-memory SDK."""

import json
import sys
import time
from pathlib import Path

import pytest

rclpy = pytest.importorskip("rclpy")
from quest2ros.msg import OVR2ROSInputs
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter
from std_msgs.msg import String

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import right_linkerhand_node as linkerhand_module
from right_linkerhand_node import RightLinkerHandNode

CLOSED = [73, 0, 0, 0, 0, 0, 156]
OPEN = [73, 0, 255, 255, 255, 255, 156]


class FakeHand:
    def __init__(self):
        self.writes = []
        self.actual = [10, 0, 10, 10, 10, 10, 156]
        self.faults = [0] * 7
        self.closed = False
        self.reads = []

    def finger_move(self, pose):
        self.writes.append(list(pose))

    def get_state(self):
        self.reads.append("state")
        return list(self.actual)

    def get_fault(self):
        self.reads.append("fault")
        return list(self.faults)

    def close(self):
        self.closed = True


@pytest.mark.parametrize("context_ok, expected_shutdowns", [(True, 1), (False, 0)])
def test_main_only_shuts_down_an_active_context(
        monkeypatch, context_ok, expected_shutdowns):
    calls = []

    class FakeNode:
        def destroy_node(self):
            calls.append("destroy")

    monkeypatch.setattr(linkerhand_module, "RightLinkerHandNode", FakeNode)
    monkeypatch.setattr(
        linkerhand_module.rclpy, "init", lambda args=None: calls.append("init"))
    monkeypatch.setattr(
        linkerhand_module.rclpy, "spin", lambda node: calls.append("spin"))
    monkeypatch.setattr(linkerhand_module.rclpy, "ok", lambda: context_ok)
    monkeypatch.setattr(
        linkerhand_module.rclpy, "shutdown", lambda: calls.append("shutdown"))

    linkerhand_module.main()

    assert calls[:3] == ["init", "spin", "destroy"]
    assert calls.count("shutdown") == expected_shutdowns


def test_main_handles_keyboard_interrupt(monkeypatch):
    calls = []

    class FakeNode:
        def destroy_node(self):
            calls.append("destroy")

    def interrupted_spin(node):
        calls.append("spin")
        raise KeyboardInterrupt

    monkeypatch.setattr(linkerhand_module, "RightLinkerHandNode", FakeNode)
    monkeypatch.setattr(
        linkerhand_module.rclpy, "init", lambda args=None: calls.append("init"))
    monkeypatch.setattr(linkerhand_module.rclpy, "spin", interrupted_spin)
    monkeypatch.setattr(linkerhand_module.rclpy, "ok", lambda: False)

    linkerhand_module.main()

    assert calls == ["init", "spin", "destroy"]


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


class Harness:
    def __init__(self, node):
        self.node = node
        self.peer = rclpy.create_node("right_linkerhand_test_peer")
        self.pub = self.peer.create_publisher(OVR2ROSInputs, "/q2r_right_hand_inputs", 10)
        self.statuses = []
        self.peer.create_subscription(
            String, "/right/linkerhand/status",
            lambda msg: self.statuses.append(json.loads(msg.data)), 10)
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(node)
        self.executor.add_node(self.peer)
        self.wait(lambda: self.pub.get_subscription_count() > 0 and self.statuses)

    def wait(self, predicate, timeout_s=3.0):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.executor.spin_once(timeout_sec=0.025)
            if predicate():
                return
        raise AssertionError("ROS test condition timed out")

    def send(self, value, predicate):
        previous = len(self.statuses)
        msg = OVR2ROSInputs()
        msg.press_index = value
        self.pub.publish(msg)
        self.wait(lambda: len(self.statuses) > previous and predicate(self.statuses[-1]))
        return self.statuses[-1]

    def settle(self, seconds=0.15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.executor.spin_once(timeout_sec=0.02)

    def close(self):
        self.executor.remove_node(self.peer)
        self.executor.remove_node(self.node)
        self.peer.destroy_node()
        self.node.destroy_node()


def hardware_node(fake, **overrides):
    parameters = {"dry_run": False, "hardware_write_enabled": True,
                  "feedback_rate_hz": 20.0, "input_timeout_s": 0.5}
    parameters.update(overrides)
    return RightLinkerHandNode(
        hand_factory=lambda **_: fake,
        parameter_overrides=[Parameter(k, value=v) for k, v in parameters.items()])


def test_dry_run_startup_toggle_and_status_without_sdk(ros):
    def forbidden_factory(**_):
        raise AssertionError("dry-run must not instantiate SDK")

    harness = Harness(RightLinkerHandNode(hand_factory=forbidden_factory))
    try:
        startup = harness.statuses[-1]
        assert startup["target"] is None
        assert startup["hand_toggle_state"] == "OPEN"
        assert startup["trigger_armed"] is True
        assert startup["actual"] is None
        assert startup["communication_ok"] is False
        first = harness.send(0.6, lambda s: s["target"] == CLOSED)
        assert first["trigger_pressed"] and first["hand_toggle_state"] == "CLOSED"
        assert first["dry_run"] and first["input_fresh"]
        assert isinstance(first["stamp"]["sec"], int)
        harness.send(0.0, lambda s: not s["trigger_pressed"])
        assert harness.statuses[-1]["target"] == CLOSED
        second = harness.send(1.0, lambda s: s["target"] == OPEN)
        assert second["hand_toggle_state"] == "OPEN"
    finally:
        harness.close()


def test_mock_hardware_one_finger_move_per_toggle(ros):
    fake = FakeHand()
    harness = Harness(hardware_node(fake))
    try:
        assert fake.reads[:2] == ["state", "fault"]
        assert fake.writes == []
        assert harness.statuses[-1]["target"] is None
        harness.send(0.6, lambda s: s["target"] == CLOSED)
        harness.wait(lambda: fake.writes == [CLOSED])
        harness.send(1.0, lambda s: s["trigger_pressed"])
        harness.settle()
        assert fake.writes == [CLOSED]
        harness.send(0.4, lambda s: not s["trigger_pressed"])
        harness.settle()
        assert fake.writes == [CLOSED]
        harness.send(0.6, lambda s: s["target"] == OPEN)
        harness.wait(lambda: fake.writes == [CLOSED, OPEN])
        assert harness.statuses[-1]["fault_codes"] == [0] * 7
        assert harness.statuses[-1]["communication_ok"]
    finally:
        harness.close()
    assert fake.closed


def test_stale_reconnect_pressed_requires_release(ros):
    fake = FakeHand()
    harness = Harness(hardware_node(fake, input_timeout_s=0.2))
    try:
        harness.send(0.6, lambda s: s["target"] == CLOSED)
        harness.wait(lambda: fake.writes == [CLOSED])
        harness.node._last_input_s = time.monotonic() - 1.0
        harness.wait(lambda: harness.statuses[-1]["state"] == "INPUT_STALE")
        assert harness.statuses[-1]["trigger_armed"] is False
        harness.send(1.0, lambda s: s["input_fresh"] and s["trigger_pressed"])
        harness.settle()
        assert fake.writes == [CLOSED]
        harness.send(0.4, lambda s: s["trigger_armed"])
        harness.send(0.6, lambda s: s["target"] == OPEN)
        harness.wait(lambda: fake.writes == [CLOSED, OPEN])
    finally:
        harness.close()


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_does_not_send_and_requires_release(ros, bad):
    fake = FakeHand()
    harness = Harness(hardware_node(fake))
    try:
        harness.send(bad, lambda s: s["invalid_input_count"] == 1)
        assert harness.statuses[-1]["target"] is None
        assert harness.statuses[-1]["trigger_value"] is None
        assert harness.statuses[-1]["trigger_armed"] is False
        assert "non-finite" in harness.statuses[-1]["error"]
        harness.send(1.0, lambda s: s["trigger_pressed"])
        harness.settle()
        assert fake.writes == []
        harness.send(0.4, lambda s: s["trigger_armed"])
        harness.send(0.6, lambda s: s["target"] == CLOSED)
        harness.wait(lambda: fake.writes == [CLOSED])
    finally:
        harness.close()


def test_existing_hand_fault_blocks_first_motion(ros):
    fake = FakeHand()
    fake.faults[2] = 7
    harness = Harness(hardware_node(fake))
    try:
        harness.send(0.6, lambda s: s["state"] == "HAND_FAULT")
        harness.settle()
        assert fake.writes == []
        assert harness.statuses[-1]["fault_codes"] == fake.faults
    finally:
        harness.close()


def test_connect_only_initializes_and_polls_but_never_moves(ros):
    fake = FakeHand()
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return fake

    node = RightLinkerHandNode(
        hand_factory=factory,
        parameter_overrides=[
            Parameter("dry_run", value=False),
            Parameter("hardware_write_enabled", value=True),
            Parameter("connect_only", value=True),
            Parameter("feedback_rate_hz", value=20.0),
        ])
    harness = Harness(node)
    try:
        assert calls == [{"hand_type": "right", "hand_joint": "L7", "modbus": "RML"}]
        assert fake.reads[:2] == ["state", "fault"]
        assert fake.writes == []
        initial = harness.statuses[-1]
        assert initial["connect_only"] is True
        assert initial["state"] == "CONNECT_ONLY"
        assert initial["target"] is None
        harness.send(1.0, lambda s: s["connect_only"])
        harness.send(0.0, lambda s: s["connect_only"])
        harness.send(1.0, lambda s: s["connect_only"])
        harness.settle()
        assert fake.writes == []
        assert harness.statuses[-1]["target"] is None
        assert fake.reads.count("state") >= 2
        assert fake.reads.count("fault") >= 2
    finally:
        harness.close()
    assert fake.closed


def test_connect_only_rejects_dry_run(ros):
    with pytest.raises(ValueError, match="connect_only"):
        RightLinkerHandNode(parameter_overrides=[
            Parameter("connect_only", value=True),
        ])


def test_hardware_gate_rejects_inconsistent_parameters(ros):
    with pytest.raises(ValueError, match="hardware_write_enabled"):
        RightLinkerHandNode(parameter_overrides=[
            Parameter("dry_run", value=True),
            Parameter("hardware_write_enabled", value=True),
        ])


def test_sdk_connection_failure_is_clear(ros):
    def failing_factory(**_):
        raise ConnectionError("mock link down")

    with pytest.raises(RuntimeError, match="mock link down"):
        RightLinkerHandNode(
            hand_factory=failing_factory,
            parameter_overrides=[
                Parameter("dry_run", value=False),
                Parameter("hardware_write_enabled", value=True),
            ])
