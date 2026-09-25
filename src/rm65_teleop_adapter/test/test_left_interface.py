"""Left endpoint and first-motion launch safety contracts, without robot output."""

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


def left_launch_module():
    launch = PACKAGE / "launch" / "left_quest_teleop.launch.py"
    spec = importlib.util.spec_from_file_location("left_quest_teleop_launch", launch)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context_for(mode="dry_run", config_file="", profile="safe", start_driver="false"):
    context = LaunchContext()
    context.launch_configurations.update({
        "mode": mode,
        "motion_profile": profile,
        "hardware_config_file": str(config_file),
        "start_rm_driver": start_driver,
    })
    return context


def session_config(tmp_path):
    config = params("left_dry_run.yaml")
    config.update({
        "dry_run": False,
        "hardware_write_enabled": True,
        "mapping_verified": True,
        "home_enabled": False,
        "follow": False,
        "max_anchor_distance_m": 0.051,
        "workspace_min": [0.089, -0.416, 0.548],
        "workspace_max": [0.099, -0.406, 0.6031],
    })
    path = tmp_path / "session.yaml"
    path.write_text(yaml.safe_dump({"left_rm65_teleop_adapter": {
        "ros__parameters": config}}), encoding="utf-8")
    return path, config


def test_left_launch_defaults_to_dry_run_and_rejects_implicit_hardware():
    module = left_launch_module()
    context = context_for()
    assert module._adapter_parameter_files(context, PACKAGE) == [
        str(PACKAGE / "config" / "left_dry_run.yaml")
    ]
    with pytest.raises(RuntimeError, match="hardware_config_file"):
        module._validate_arguments(context_for(mode="hardware"))
    with pytest.raises(RuntimeError, match="driver separately"):
        module._validate_arguments(context_for(start_driver="true"))


def test_left_hardware_accepts_only_explicit_narrow_safe_config(tmp_path):
    module = left_launch_module()
    path, config = session_config(tmp_path)
    context = context_for(mode="hardware", config_file=path)
    assert module._adapter_parameter_files(context, PACKAGE) == [str(path)]
    with pytest.raises(RuntimeError, match="safe motion profile only"):
        module._validate_arguments(context_for(
            mode="hardware", config_file=path, profile="normal"))

    config["workspace_max"][2] = 1.5
    path.write_text(yaml.safe_dump({"left_rm65_teleop_adapter": {
        "ros__parameters": config}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="narrow \\+Z box"):
        module._adapter_parameter_files(context, PACKAGE)


def test_left_hardware_rejects_wrong_owner_and_widened_watchdog(tmp_path):
    module = left_launch_module()
    path, config = session_config(tmp_path)
    context = context_for(mode="hardware", config_file=path)
    config["expected_driver_node"] = "/right/rm_driver"
    path.write_text(yaml.safe_dump({"left_rm65_teleop_adapter": {
        "ros__parameters": config}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="endpoint mismatch"):
        module._adapter_parameter_files(context, PACKAGE)

    config["expected_driver_node"] = "/left/rm_driver"
    config["inputs_timeout"] = 1.0
    path.write_text(yaml.safe_dump({"left_rm65_teleop_adapter": {
        "ros__parameters": config}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="watchdog change rejected"):
        module._adapter_parameter_files(context, PACKAGE)
