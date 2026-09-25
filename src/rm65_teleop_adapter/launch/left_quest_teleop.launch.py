"""Left Quest preview or one bounded Cartesian hardware session."""

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
    "command_topic": "/left/rm_driver/movep_canfd_cmd",
    "home_movej_topic": "/left/rm_driver/movej_canfd_cmd",
    "stop_topic": "/left/rm_driver/move_stop_cmd",
}
LEFT_HARDWARE_PROFILES = ("safe", "left_test")
LEFT_TEST_VALUES = {
    "translation_scale": 1.0,
    "max_velocity_mps": 0.02,
    "max_step_m": 0.00010,
    "max_anchor_distance_m": 0.051,
}


def _validate_arguments(context):
    mode = LaunchConfiguration("mode").perform(context)
    if mode not in ("dry_run", "hardware"):
        raise RuntimeError("left mode must be dry_run or hardware")
    if LaunchConfiguration("start_rm_driver").perform(context).lower() != "false":
        raise RuntimeError("start the left-only RM driver separately")
    if mode == "hardware":
        if LaunchConfiguration("motion_profile").perform(context) not in LEFT_HARDWARE_PROFILES:
            raise RuntimeError("left hardware permits safe or left_test motion profile only")
        path = Path(LaunchConfiguration("hardware_config_file").perform(context))
        if not path.is_absolute() or not path.is_file():
            raise RuntimeError("left hardware requires an absolute session hardware_config_file")
    return []


def _validate_hardware_config(config_path, package_share):
    try:
        document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        params = document["left_rm65_teleop_adapter"]["ros__parameters"]
        safe_doc = yaml.safe_load(
            (Path(package_share) / "config" / "motion_profiles" / "safe.yaml")
            .read_text(encoding="utf-8"))
        safe = safe_doc["rm65_teleop_adapter"]["ros__parameters"]
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("invalid left session hardware config") from exc
    for key, value in LEFT_HARDWARE_ENDPOINTS.items():
        if params.get(key) != value:
            raise RuntimeError(f"left hardware endpoint mismatch: {key}")
    for key, value in {"dry_run": False, "hardware_write_enabled": True,
                       "mapping_verified": True, "home_enabled": False,
                       "follow": False}.items():
        if params.get(key) is not value:
            raise RuntimeError(f"left hardware gate mismatch: {key}")
    if any(key in params for key in
           ("home_action_name", "home_joint_degrees", "home_joint_names")):
        raise RuntimeError("left Home must remain unconfigured")
    if params.get("mapping") != [0.0, 0.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 0.0]:
        raise RuntimeError("left first-motion mapping mismatch")
    for key in ("translation_scale", "max_velocity_mps", "max_step_m"):
        if params.get(key) != safe[key]:
            raise RuntimeError(f"left first-motion {key} must equal safe profile")
    if params.get("max_anchor_distance_m") != 0.051:
        raise RuntimeError("left first-motion anchor cap must be 0.051 m")
    for key, value in {"target_timeout": 0.20, "quest_pose_timeout": 0.20,
                       "inputs_timeout": 0.20, "robot_timeout": 0.10}.items():
        if params.get(key) != value:
            raise RuntimeError(f"left watchdog change rejected: {key}")
    bounds = [params.get("workspace_min"), params.get("workspace_max")]
    if any(not isinstance(b, list) or len(b) != 3 for b in bounds):
        raise RuntimeError("left first-motion workspace must have three axes")
    try:
        widths = [float(hi) - float(lo) for lo, hi in zip(*bounds)]
        finite = all(math.isfinite(float(v)) for b in bounds for v in b)
    except (TypeError, ValueError):
        finite = False
        widths = []
    if not finite or any(w <= 0 for w in widths) or any(
        abs(actual - expected) > 1e-6
        for actual, expected in zip(widths, (0.010, 0.010, 0.0551))
    ):
        raise RuntimeError("left first-motion workspace must be a narrow +Z box")


def _validate_left_test_profile(profile_path):
    try:
        document = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError("invalid left_test motion profile") from exc
    expected = {"left_rm65_teleop_adapter": {"ros__parameters": LEFT_TEST_VALUES}}
    if document != expected or any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in document["left_rm65_teleop_adapter"]["ros__parameters"].values()
    ):
        raise RuntimeError("left_test profile must contain only the four approved motion values")


def _adapter_parameter_files(context, package_share):
    _validate_arguments(context)
    if LaunchConfiguration("mode").perform(context) == "dry_run":
        return [str(Path(package_share) / "config" / "left_dry_run.yaml")]
    config_path = Path(LaunchConfiguration("hardware_config_file").perform(context))
    _validate_hardware_config(config_path, package_share)
    if LaunchConfiguration("motion_profile").perform(context) == "safe":
        return [str(config_path)]
    profile_path = Path(package_share) / "config" / "motion_profiles" / "left_test.yaml"
    _validate_left_test_profile(profile_path)
    return [str(config_path), str(profile_path)]


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
        DeclareLaunchArgument("hardware_config_file", default_value=""),
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
