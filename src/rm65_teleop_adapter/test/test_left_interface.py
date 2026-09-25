"""Left software interface contracts; no robot graph or hardware commands."""

import importlib.util
from pathlib import Path

import pytest
import yaml
from launch import LaunchContext


PACKAGE = Path(__file__).parents[1]
RIGHT_TOPICS = {
    "expected_adapter_node": "/rm65_teleop_adapter",
    "expected_driver_node": "/right/rm_driver",
    "expected_control_node": "/right/rm_control",
    "quest_pose_topic": "/q2r_right_hand_pose",
    "inputs_topic": "/q2r_right_hand_inputs",
    "target_topic": "/quest_right_target_pose",
    "robot_pose_topic": "/right/rm_driver/udp_arm_position",
    "joint_state_topic": "/right/joint_states",
    "command_topic": "/right/rm_driver/movep_canfd_cmd",
    "home_movej_topic": "/right/rm_driver/movej_canfd_cmd",
    "stop_topic": "/right/rm_driver/move_stop_cmd",
    "home_action_name": "/right/rm_group_controller/follow_joint_trajectory",
    "status_topic": "/right/rm65_teleop/status",
    "preview_topic": "/right/rm65_teleop/preview_target_pose",
    "clear_fault_service": "/right/rm65_teleop/clear_fault",
}
LEFT_TOPICS = {
    "expected_adapter_node": "/left_rm65_teleop_adapter",
    "expected_driver_node": "/left/rm_driver",
    "expected_control_node": "/left/rm_control",
    "quest_pose_topic": "/q2r_left_hand_pose",
    "inputs_topic": "/q2r_left_hand_inputs",
    "target_topic": "/quest_left_target_pose",
    "robot_pose_topic": "/left/rm_driver/udp_arm_position",
    "joint_state_topic": "/left/joint_states",
    "command_topic": "/left/rm_driver/movep_canfd_cmd",
    "home_movej_topic": "/left/rm_driver/movej_canfd_cmd",
    "stop_topic": "/left/rm_driver/move_stop_cmd",
    "status_topic": "/left/rm65_teleop/status",
    "preview_topic": "/left/rm65_teleop/preview_target_pose",
    "clear_fault_service": "/left/rm65_teleop/clear_fault",
}


def params(name):
    with (PACKAGE / "config" / name).open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    node = "left_rm65_teleop_adapter" if name == "left_dry_run.yaml" else "rm65_teleop_adapter"
    return document[node]["ros__parameters"]


def test_right_endpoints_remain_exact():
    right = params("hardware.yaml")
    for key, value in RIGHT_TOPICS.items():
        assert right[key] == value, key
    assert right["mapping"] == [0.0, 0.0, 1.0, -1.0, 0.0, 0.0, 0.0, -1.0, 0.0]
    assert right["home_enabled"] is True


def test_left_config_is_isolated_and_fail_closed():
    left = params("left_dry_run.yaml")
    for key, value in LEFT_TOPICS.items():
        assert left[key] == value, key
    assert left["dry_run"] is True
    assert left["hardware_write_enabled"] is False
    assert left["mapping_verified"] is False
    assert left["home_enabled"] is False
    assert left["mapping"] == [0.0, 0.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    assert "home_joint_degrees" not in left
    assert "home_button_field" not in left
    assert "home_action_name" not in left


def test_left_launch_cannot_enter_hardware_mode():
    launch = PACKAGE / "launch" / "left_quest_teleop.launch.py"
    spec = importlib.util.spec_from_file_location("left_quest_teleop_launch", launch)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = LaunchContext()
    context.launch_configurations["mode"] = "hardware"
    with pytest.raises(RuntimeError, match="dry_run"):
        module._validate_arguments(context)
    context.launch_configurations["mode"] = "dry_run"
    assert module._adapter_parameter_files(context, PACKAGE) == [
        str(PACKAGE / "config" / "left_dry_run.yaml")
    ]
