from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


MOTION_PROFILES = ("safe", "normal", "fast")


def _validate_arguments(context):
    mode = LaunchConfiguration("mode").perform(context)
    if mode not in ("dry_run", "hardware"):
        raise RuntimeError("mode must be either 'dry_run' or 'hardware'")
    motion_profile = LaunchConfiguration("motion_profile").perform(context)
    if motion_profile not in MOTION_PROFILES:
        raise RuntimeError("motion_profile must be one of: safe, normal, fast")
    if IfCondition(LaunchConfiguration("start_rm_driver")).evaluate(context):
        raise RuntimeError(
            "start_rm_driver is not supported: the installed RM driver has no "
            "verified right-only launch; start the right RM65 driver separately"
        )
    return []


def _adapter_parameter_files(context, package_share):
    mode = LaunchConfiguration("mode").perform(context)
    config_dir = Path(package_share) / "config"
    if mode == "dry_run":
        return [str(config_dir / "dry_run.yaml")]
    motion_profile = LaunchConfiguration("motion_profile").perform(context)
    return [
        str(config_dir / "hardware.yaml"),
        str(config_dir / "motion_profiles" / f"{motion_profile}.yaml"),
    ]


def _adapter_node(context):
    mode = LaunchConfiguration("mode").perform(context)
    motion_profile = LaunchConfiguration("motion_profile").perform(context)
    package_share = Path(get_package_share_directory("rm65_teleop_adapter"))
    return [
        LogInfo(msg=f"right teleop mode={mode.upper()} motion_profile={motion_profile}"),
        Node(
            package="rm65_teleop_adapter",
            executable="rm65_teleop_adapter_node",
            name="rm65_teleop_adapter",
            output="screen",
            parameters=_adapter_parameter_files(context, package_share),
        )
    ]


def generate_launch_description():
    package_share = Path(get_package_share_directory("rm65_teleop_adapter"))
    tcp_share = Path(get_package_share_directory("ros_tcp_endpoint"))
    rviz_config = package_share / "config" / "right_quest_teleop.rviz"

    return LaunchDescription([
        DeclareLaunchArgument(
            "mode",
            default_value="dry_run",
            description="Adapter profile: dry_run or hardware",
        ),
        DeclareLaunchArgument(
            "motion_profile",
            default_value="safe",
            description="Motion profile: safe, normal, or fast",
        ),
        DeclareLaunchArgument(
            "use_rviz",
            default_value="false",
            description="Start RViz with the right-target view",
        ),
        DeclareLaunchArgument(
            "start_tcp",
            default_value="true",
            description="Start the ROS TCP endpoint on port 10000",
        ),
        DeclareLaunchArgument(
            "start_bridge",
            default_value="true",
            description="Start the Quest right-target bridge",
        ),
        DeclareLaunchArgument(
            "start_status",
            default_value="true",
            description="Start the read-only teleop status monitor",
        ),
        DeclareLaunchArgument(
            "start_rm_driver",
            default_value="false",
            description="Reserved until a verified right-only RM65 launch exists",
        ),
        OpaqueFunction(function=_validate_arguments),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(tcp_share / "launch" / "endpoint.py")),
            condition=IfCondition(LaunchConfiguration("start_tcp")),
        ),
        Node(
            package="q2r2_bringup",
            executable="quest_right_target_bridge",
            name="quest_right_target_bridge",
            output="screen",
            condition=IfCondition(LaunchConfiguration("start_bridge")),
        ),
        OpaqueFunction(function=_adapter_node),
        Node(
            package="rm65_teleop_adapter",
            executable="teleop_status_monitor",
            name="teleop_status_monitor",
            output="screen",
            condition=IfCondition(LaunchConfiguration("start_status")),
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="right_quest_teleop_rviz",
            output="screen",
            arguments=["-d", str(rviz_config)],
            condition=IfCondition(LaunchConfiguration("use_rviz")),
        ),
    ])
