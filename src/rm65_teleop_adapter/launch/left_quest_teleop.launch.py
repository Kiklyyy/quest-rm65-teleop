"""Software-only Quest left-hand RM65 preview; no left hardware outputs."""

from pathlib import Path

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


def _validate_arguments(context):
    if LaunchConfiguration("mode").perform(context) != "dry_run":
        raise RuntimeError("left launch permits dry_run only; hardware is not validated")
    return []


def _adapter_parameter_files(context, package_share):
    _validate_arguments(context)
    return [str(Path(package_share) / "config" / "left_dry_run.yaml")]


def _adapter_node(context):
    package_share = Path(get_package_share_directory("rm65_teleop_adapter"))
    return [
        LogInfo(msg="left teleop DRY_RUN only; no left RM65 hardware publisher"),
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
