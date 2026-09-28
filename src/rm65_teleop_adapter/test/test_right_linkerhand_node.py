"""Isolated ROS tests: synthetic Quest Inputs and an in-memory SDK stand-in."""

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
from right_linkerhand_node import RightLinkerHandNode


class FakeHand:
    def __init__(self):
        self.writes = []
        self.actual = [10, 0, 10, 10, 10, 10, 255]
        self.faults = [0] * 7
        self.closed = False

    def finger_move(self, pose):
        self.writes.append(list(pose))

    def get_state(self):
        return list(self.actual)

    def get_fault(self):
        return list(self.faults)

    def close(self):
        self.closed = True


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


def spin_until(executor, predicate, timeout_s=3.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.05)
        if predicate():
            return
    raise AssertionError("ROS test condition timed out")


def exercise_node(node, values, predicate):
    peer = rclpy.create_node("right_linkerhand_test_peer")
    pub = peer.create_publisher(OVR2ROSInputs, "/q2r_right_hand_inputs", 10)
    statuses = []
    peer.create_subscription(
        String, "/right/linkerhand/status",
        lambda msg: statuses.append(json.loads(msg.data)), 10)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(peer)
    try:
        for value in values:
            msg = OVR2ROSInputs()
            msg.press_index = value
            spin_until(executor, lambda: pub.get_subscription_count() > 0)
            pub.publish(msg)
            spin_until(executor, lambda: predicate(statuses, value))
        return statuses
    finally:
        executor.remove_node(peer)
        executor.remove_node(node)
        peer.destroy_node()
        node.destroy_node()


def test_dry_run_maps_quest_topic_and_reports_status_without_sdk(ros):
    def forbidden_factory(**_):
        raise AssertionError("dry-run must not instantiate SDK")

    node = RightLinkerHandNode(hand_factory=forbidden_factory)
    expected = {
        0.0: [255, 0, 255, 255, 255, 255, 255],
        0.5: [128, 0, 128, 128, 128, 128, 255],
        1.0: [0, 0, 0, 0, 0, 0, 255],
    }
    statuses = exercise_node(
        node, [0.0, 0.5, 1.0],
        lambda received, value: any(s["target"] == expected[value] for s in received))
    for target in expected.values():
        match = next(s for s in statuses if s["target"] == target)
        assert match["dry_run"] is True
        assert match["actual"] is None
        assert match["fault_codes"] is None
        assert match["communication_ok"] is False
        assert match["input_fresh"] is True
        assert isinstance(match["stamp"]["sec"], int)


def test_nonfinite_quest_input_opens_hand_and_reports_diagnostic(ros):
    node = RightLinkerHandNode()
    statuses = exercise_node(
        node, [float("nan")],
        lambda received, _: any(
            s["target"] == [255, 0, 255, 255, 255, 255, 255]
            and s["invalid_input_count"] == 1
            and "non-finite" in s["error"] for s in received))
    assert statuses[-1]["state"] == "DRY_RUN"


def test_fake_sdk_receives_only_changed_targets_and_reports_feedback(ros):
    fake = FakeHand()
    node = RightLinkerHandNode(
        hand_factory=lambda **kwargs: fake,
        parameter_overrides=[
            Parameter("dry_run", value=False),
            Parameter("hardware_write_enabled", value=True),
            Parameter("input_timeout_s", value=0.2),
            Parameter("feedback_rate_hz", value=20.0),
        ])
    statuses = exercise_node(
        node, [0.5, 1.0],
        lambda received, value: any(
            s["target"] == ([128, 0, 128, 128, 128, 128, 255] if value == 0.5
                            else [0, 0, 0, 0, 0, 0, 255])
            and s["actual"] == fake.actual and s["communication_ok"]
            for s in received) and bool(fake.writes) and fake.writes[-1] == (
                [128, 0, 128, 128, 128, 128, 255] if value == 0.5
                else [0, 0, 0, 0, 0, 0, 255]))
    assert fake.writes == [
        [128, 0, 128, 128, 128, 128, 255],
        [0, 0, 0, 0, 0, 0, 255],
    ]
    assert statuses[-1]["fault_codes"] == [0] * 7
    assert fake.closed


def test_existing_hand_fault_blocks_first_motion_and_is_reported(ros):
    fake = FakeHand()
    fake.faults[2] = 7
    node = RightLinkerHandNode(
        hand_factory=lambda **kwargs: fake,
        parameter_overrides=[
            Parameter("dry_run", value=False),
            Parameter("hardware_write_enabled", value=True),
            Parameter("feedback_rate_hz", value=1.0),
            Parameter("input_timeout_s", value=2.0),
        ])
    statuses = exercise_node(
        node, [1.0],
        lambda received, _: any(s["state"] == "HAND_FAULT" and
                                s["fault_codes"] == fake.faults for s in received))
    assert fake.writes == []
    assert any(s["state"] == "HAND_FAULT" for s in statuses)


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
