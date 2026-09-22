import inspect
import struct
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest
from builtin_interfaces.msg import Time
from geometry_msgs.msg import PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.node import Node
from visualization_msgs.msg import Marker

from q2r2_bringup.quest_right_target_bridge import (
    INPUTS_TOPIC, MARKER_COLOR_RGBA, MARKER_ID, MARKER_NAMESPACE,
    MARKER_SCALE_M, POSE_TOPIC, TARGET_MARKER_TOPIC, TARGET_POSE_TOPIC,
    TIMER_PERIOD_S, WORLD_FRAME, QuestRightTargetBridge,
    build_target_marker, build_target_pose,
)

TARGET = (0.6, -0.2, 0.8)


def make_stamp() -> Time:
    return Time(sec=12, nanosec=345)


def test_topic_and_timer_constants_are_exact():
    assert POSE_TOPIC == "/q2r_right_hand_pose"
    assert INPUTS_TOPIC == "/q2r_right_hand_inputs"
    assert TARGET_POSE_TOPIC == "/quest_right_target_pose"
    assert TARGET_MARKER_TOPIC == "/quest_right_target_marker"
    assert TIMER_PERIOD_S == 0.02
    assert WORLD_FRAME == "world"


def test_build_target_pose_fields():
    stamp = make_stamp()
    message = build_target_pose(TARGET, stamp)
    assert message.header.frame_id == "world"
    assert (message.header.stamp.sec, message.header.stamp.nanosec) == (12, 345)
    assert (message.pose.position.x, message.pose.position.y, message.pose.position.z) == TARGET
    assert (message.pose.orientation.x, message.pose.orientation.y, message.pose.orientation.z, message.pose.orientation.w) == (0.0, 0.0, 0.0, 1.0)


def test_build_target_marker_fields():
    stamp = make_stamp()
    marker = build_target_marker(TARGET, stamp)
    assert marker.header.frame_id == "world"
    assert (marker.header.stamp.sec, marker.header.stamp.nanosec) == (12, 345)
    assert marker.ns == MARKER_NAMESPACE == "quest_right_target"
    assert marker.id == MARKER_ID == 0
    assert marker.type == Marker.SPHERE
    assert marker.action == Marker.ADD
    assert (marker.pose.position.x, marker.pose.position.y, marker.pose.position.z) == TARGET
    assert (marker.pose.orientation.x, marker.pose.orientation.y, marker.pose.orientation.z, marker.pose.orientation.w) == (0.0, 0.0, 0.0, 1.0)
    assert marker.scale.x == MARKER_SCALE_M == 0.06
    assert marker.scale.y == MARKER_SCALE_M
    assert marker.scale.z == MARKER_SCALE_M
    assert (marker.color.r, marker.color.g, marker.color.b, marker.color.a) == pytest.approx(MARKER_COLOR_RGBA)
    assert marker.lifetime.sec == 0
    assert marker.lifetime.nanosec == 0


def test_node_name_topics_types_and_timer_are_wired_exactly():
    with (
        patch.object(Node, "__init__", return_value=None) as node_init,
        patch.object(Node, "create_subscription") as create_subscription,
        patch.object(Node, "create_publisher") as create_publisher,
        patch.object(Node, "create_timer") as create_timer,
    ):
        bridge = QuestRightTargetBridge()
    node_init.assert_called_once_with("quest_right_target_bridge")
    assert create_subscription.call_count == 2
    assert create_subscription.call_args_list[0].args == (PoseStamped, POSE_TOPIC, bridge._pose_callback, 10)
    assert create_subscription.call_args_list[1].args == (OVR2ROSInputs, INPUTS_TOPIC, bridge._inputs_callback, 10)
    assert create_publisher.call_count == 2
    assert create_publisher.call_args_list[0].args == (PoseStamped, TARGET_POSE_TOPIC, 10)
    assert create_publisher.call_args_list[1].args == (Marker, TARGET_MARKER_TOPIC, 10)
    create_timer.assert_called_once_with(TIMER_PERIOD_S, bridge._timer_callback)


def test_pose_callback_passes_only_xyz_and_monotonic_time():
    bridge = QuestRightTargetBridge.__new__(QuestRightTargetBridge)
    bridge._logic = Mock()
    message = PoseStamped()
    message.header.frame_id = "ignored"
    message.pose.position.x, message.pose.position.y, message.pose.position.z = 1.0, 2.0, 3.0
    message.pose.orientation.w = 0.25
    with patch("q2r2_bringup.quest_right_target_bridge.time.monotonic", return_value=10.0):
        bridge._pose_callback(message)
    bridge._logic.update_pose.assert_called_once_with((1.0, 2.0, 3.0), 10.0)
    source = inspect.getsource(QuestRightTargetBridge._pose_callback)
    assert "msg.header" not in source
    assert "orientation" not in source


def make_bridge_for_inputs_callback() -> QuestRightTargetBridge:
    bridge = QuestRightTargetBridge.__new__(QuestRightTargetBridge)
    bridge._logic = Mock()
    bridge._deadman_pressed = False
    return bridge


def send_inputs(
    bridge: QuestRightTargetBridge,
    press_middle: float,
    now_s: float,
    *,
    button_lower: bool = False,
) -> None:
    message = OVR2ROSInputs()
    message.press_middle = press_middle
    message.button_lower = button_lower
    with patch(
        "q2r2_bringup.quest_right_target_bridge.time.monotonic",
        return_value=now_s,
    ):
        bridge._inputs_callback(message)


def test_middle_grip_press_threshold_activates_deadman():
    bridge = make_bridge_for_inputs_callback()

    send_inputs(bridge, 0.0, 10.0)
    send_inputs(bridge, 0.60, 11.0)
    send_inputs(bridge, 1.0, 12.0)

    assert bridge._logic.update_deadman.call_args_list == [
        call(False, 10.0),
        call(True, 11.0),
        call(True, 12.0),
    ]


def test_middle_grip_pressed_state_holds_until_release_threshold():
    bridge = make_bridge_for_inputs_callback()

    for index, value in enumerate((0.60, 0.59, 0.50, 0.41, 0.40)):
        send_inputs(bridge, value, 20.0 + index)

    assert [item.args[0] for item in bridge._logic.update_deadman.call_args_list] == [
        True,
        True,
        True,
        True,
        False,
    ]


def test_float32_wire_value_at_release_threshold_releases():
    bridge = make_bridge_for_inputs_callback()
    wire_press = struct.unpack("f", struct.pack("f", 0.60))[0]
    wire_release = struct.unpack("f", struct.pack("f", 0.40))[0]
    send_inputs(bridge, wire_press, 25.0)

    send_inputs(bridge, wire_release, 26.0)

    assert bridge._logic.update_deadman.call_args_list[-1] == call(False, 26.0)


def test_middle_grip_released_state_holds_below_press_threshold():
    bridge = make_bridge_for_inputs_callback()

    for index, value in enumerate((0.0, 0.41, 0.50, 0.59)):
        send_inputs(bridge, value, 30.0 + index)

    assert [item.args[0] for item in bridge._logic.update_deadman.call_args_list] == [
        False,
        False,
        False,
        False,
    ]


def test_button_lower_cannot_activate_deadman():
    bridge = make_bridge_for_inputs_callback()

    send_inputs(bridge, 0.0, 40.0, button_lower=True)

    bridge._logic.update_deadman.assert_called_once_with(False, 40.0)
    source = inspect.getsource(QuestRightTargetBridge._inputs_callback)
    assert "button_lower" not in source
    assert "button_upper" not in source
    assert "thumb_stick" not in source
    assert "press_index" not in source
    assert "press_middle" in source


@pytest.mark.parametrize("non_finite", (float("nan"), float("inf"), float("-inf")))
def test_nonfinite_middle_grip_safely_releases_deadman(non_finite):
    bridge = make_bridge_for_inputs_callback()
    send_inputs(bridge, 0.60, 50.0)

    send_inputs(bridge, non_finite, 51.0)

    assert bridge._logic.update_deadman.call_args_list[-1] == call(False, 51.0)


def test_timer_checks_watchdog_and_continuously_publishes_same_target():
    bridge = QuestRightTargetBridge.__new__(QuestRightTargetBridge)
    bridge._logic = Mock()
    bridge._logic.target = TARGET
    bridge._target_pose_publisher = Mock()
    bridge._target_marker_publisher = Mock()
    stamp = make_stamp()
    clock = Mock()
    clock.now.return_value.to_msg.return_value = stamp
    with (
        patch.object(QuestRightTargetBridge, "get_clock", return_value=clock),
        patch("q2r2_bringup.quest_right_target_bridge.time.monotonic", return_value=12.0),
    ):
        bridge._timer_callback()
        bridge._timer_callback()
    assert bridge._logic.check_timeout.call_args_list == [call(12.0), call(12.0)]
    assert bridge._target_pose_publisher.publish.call_count == 2
    assert bridge._target_marker_publisher.publish.call_count == 2
    pose = bridge._target_pose_publisher.publish.call_args_list[0].args[0]
    marker = bridge._target_marker_publisher.publish.call_args_list[0].args[0]
    assert (pose.pose.position.x, pose.pose.position.y, pose.pose.position.z) == TARGET
    assert (marker.pose.position.x, marker.pose.position.y, marker.pose.position.z) == TARGET
    assert pose.header.stamp.sec == marker.header.stamp.sec == stamp.sec
    assert pose.header.stamp.nanosec == marker.header.stamp.nanosec == stamp.nanosec


def test_bridge_source_has_no_robot_control_interface():
    module_path = Path(inspect.getfile(QuestRightTargetBridge))
    source = module_path.read_text(encoding="utf-8")
    forbidden = ('"/left/', '"/right/', "rm_driver", "rm_control", "FollowJointTrajectory", "GripperCommand", "robot_arm_controller_base", "ActionClient", "rclpy.action", "control_msgs")
    for token in forbidden:
        assert token not in source


def test_setup_entry_point_is_added_without_removing_existing_entries():
    setup_path = Path(__file__).resolve().parents[1] / "setup.py"
    source = setup_path.read_text(encoding="utf-8")
    expected_entries = (
        "ros2quest = q2r2_bringup.ros2quest:main",
        "SimulationInput = q2r2_bringup.SimulationInput:main",
        "CheckTCPconnection = q2r2_bringup.CheckTCPconnection:main",
        "left_arm_controller = q2r2_bringup.left_arm_controller:main",
        "right_arm_controller = q2r2_bringup.right_arm_controller:main",
        "quest_right_target_bridge = q2r2_bringup.quest_right_target_bridge:main",
    )
    for entry in expected_entries:
        assert entry in source
