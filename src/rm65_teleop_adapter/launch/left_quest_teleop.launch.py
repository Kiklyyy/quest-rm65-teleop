"""Left Quest preview or explicitly enabled hardware teleop and Home."""

import math
from pathlib import Path

import yaml

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


LEFT_BRIDGE = {
    "pose_topic": "/q2r_left_hand_pose",
    "inputs_topic": "/q2r_left_hand_inputs",
    "target_topic": "/quest_left_target_pose",
    "marker_topic": "/quest_left_target_marker",
    "frame_id": "world",
    "marker_namespace": "quest_left_target",
}
LEFT_MONITOR = {
    "quest_pose_topic": "/q2r_left_hand_pose",
    "inputs_topic": "/q2r_left_hand_inputs",
    "target_topic": "/quest_left_target_pose",
    "robot_pose_topic": "/left/rm_driver/udp_arm_position",
    "joint_state_topic": "/left/joint_states",
    "status_topic": "/left/rm65_teleop/status",
}
LEFT_HARDWARE_ENDPOINTS = {
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
    "preview_frame_id": "left_rm65_base",
}
LEFT_HARDWARE_PROFILES = ("safe", "normal")
MOTION_KEYS = ("translation_scale", "max_velocity_mps", "max_step_m", "max_anchor_distance_m")
SHARED_SAFETY_KEYS = (
    "joint_state_timeout", "control_rate_hz", "max_control_period", "follow",
    "stop_repeat_count", "target_timeout", "quest_pose_timeout", "inputs_timeout",
    "robot_timeout", "unexpected_target_jump_m", "rotation_scale",
    "max_angular_velocity_rad_s", "max_angular_step_rad",
    "unexpected_orientation_jump_rad", "workspace_min", "workspace_max",
)


def _validate_arguments(context):
    mode = LaunchConfiguration("mode").perform(context)
    if mode not in ("dry_run", "hardware"):
        raise RuntimeError("left mode must be dry_run or hardware")
    if LaunchConfiguration("start_rm_driver").perform(context).lower() != "false":
        raise RuntimeError("start the left-only RM driver separately")
    if mode == "hardware":
        if LaunchConfiguration("motion_profile").perform(context) not in LEFT_HARDWARE_PROFILES:
            raise RuntimeError("left hardware permits safe or normal motion profile only")
    return []


def _read_params(path, node):
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        common = document.get("/**", {}).get("ros__parameters", {})
        specific = document[node]["ros__parameters"]
        return {**common, **specific}
    except (OSError, AttributeError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise RuntimeError(f"invalid parameter file: {path}") from exc


def _validate_hardware_config(config_path, package_share):
    params = _read_params(config_path, "left_rm65_teleop_adapter")
    right = _read_params(config_path, "rm65_teleop_adapter")
    for key, value in LEFT_HARDWARE_ENDPOINTS.items():
        if params.get(key) != value:
            raise RuntimeError(f"left hardware endpoint mismatch: {key}")
    for key, value in {"dry_run": False, "hardware_write_enabled": True,
                       "mapping_verified": True, "home_enabled": True,
                       "follow": False}.items():
        if params.get(key) is not value:
            raise RuntimeError(f"left hardware gate mismatch: {key}")
    for key, value in {
        "home_button_field": "upper",
        "home_hold_seconds": 1.5,
        "home_speed_deg_s": 15.0,
        "home_action_name": "/left/rm_group_controller/follow_joint_trajectory",
        "home_joint_names": [f"joint{i}" for i in range(1, 7)],
    }.items():
        if params.get(key) != value:
            raise RuntimeError(f"left Home config mismatch: {key}")
    degrees = params.get("home_joint_degrees")
    if not isinstance(degrees, list) or len(degrees) != 6 or any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) for value in degrees
    ):
        raise RuntimeError("left Home target must have six finite degrees")
    if params.get("mapping") != [0.0, 0.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 0.0]:
        raise RuntimeError("left mapping mismatch")
    for key in SHARED_SAFETY_KEYS:
        if params.get(key) != right.get(key):
            raise RuntimeError(f"left hardware safety mismatch: {key}")
    if params.get("max_anchor_angle_rad") != math.pi / 2:
        raise RuntimeError("left hardware safety mismatch: max_anchor_angle_rad")
    safe = _read_params(Path(package_share) / "config" / "motion_profiles" / "safe.yaml",
                        "rm65_teleop_adapter")
    for key in MOTION_KEYS:
        if params.get(key) != right.get(key) or params.get(key) != safe.get(key):
            raise RuntimeError(f"left base motion mismatch: {key}")


def _normal_overlay(package_share):
    path = Path(package_share) / "config" / "motion_profiles" / "normal.yaml"
    params = _read_params(path, "rm65_teleop_adapter")
    if set(params) != set(MOTION_KEYS) or any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) or value <= 0
        for value in params.values()
    ):
        raise RuntimeError("normal profile must contain four finite positive motion values")
    return params


def _adapter_parameter_files(context, package_share):
    _validate_arguments(context)
    if LaunchConfiguration("mode").perform(context) == "dry_run":
        return [str(Path(package_share) / "config" / "left_dry_run.yaml")]
    config_path = Path(package_share) / "config" / "hardware.yaml"
    profile = LaunchConfiguration("motion_profile").perform(context)
    _validate_hardware_config(config_path, package_share)
    if profile == "safe":
        return [str(config_path)]
    return [str(config_path), _normal_overlay(package_share)]


def _adapter_node(context):
    package_share = Path(get_package_share_directory("rm65_teleop_adapter"))
    mode = LaunchConfiguration("mode").perform(context)
    profile = LaunchConfiguration("motion_profile").perform(context)
    return [
        LogInfo(msg=f"left teleop mode={mode.upper()} motion_profile={profile}"),
        Node(
            package="rm65_teleop_adapter",
            executable="rm65_teleop_adapter_node",
            name="left_rm65_teleop_adapter",
            output="screen",
            parameters=_adapter_parameter_files(context, package_share),
        ),
    ]


def generate_launch_description():
    package_share = Path(get_package_share_directory("rm65_teleop_adapter"))
    tcp_share = Path(get_package_share_directory("ros_tcp_endpoint"))
    rviz_config = package_share / "config" / "left_quest_teleop.rviz"
    return LaunchDescription([
        DeclareLaunchArgument("mode", default_value="dry_run"),
        DeclareLaunchArgument("motion_profile", default_value="safe"),
        DeclareLaunchArgument("start_rm_driver", default_value="false"),
        DeclareLaunchArgument("use_rviz", default_value="false"),
        # A live endpoint may already own TCP port 10000. Opt in only after checking.
        DeclareLaunchArgument("start_tcp", default_value="false"),
        DeclareLaunchArgument("start_bridge", default_value="true"),
        DeclareLaunchArgument("start_status", default_value="true"),
        OpaqueFunction(function=_validate_arguments),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(tcp_share / "launch" / "endpoint.py")),
            condition=IfCondition(LaunchConfiguration("start_tcp")),
        ),
        Node(
            package="q2r2_bringup", executable="quest_target_bridge",
            name="quest_left_target_bridge", output="screen",
            parameters=[LEFT_BRIDGE],
            condition=IfCondition(LaunchConfiguration("start_bridge")),
        ),
        OpaqueFunction(function=_adapter_node),
        Node(
            package="rm65_teleop_adapter", executable="teleop_status_monitor",
            name="left_teleop_status_monitor", output="screen",
            parameters=[LEFT_MONITOR],
            condition=IfCondition(LaunchConfiguration("start_status")),
        ),
        Node(
            package="rviz2", executable="rviz2",
            name="left_quest_teleop_rviz", output="screen",
            arguments=["-d", str(rviz_config)],
            condition=IfCondition(LaunchConfiguration("use_rviz")),
        ),
    ])
