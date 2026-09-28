"""Bring up both RM65 arms, both Quest adapters, and optional right O7 hand."""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


MOTION_PROFILES = ("safe", "normal")


def _enabled(context, name):
    return IfCondition(LaunchConfiguration(name)).evaluate(context)


def _validate_arguments(context):
    mode = LaunchConfiguration("mode").perform(context)
    if mode not in ("dry_run", "hardware"):
        raise RuntimeError("mode must be either dry_run or hardware")

    profile = LaunchConfiguration("motion_profile").perform(context)
    if profile not in MOTION_PROFILES:
        raise RuntimeError("dual-arm motion_profile must be safe or normal")

    if _enabled(context, "linkerhand_connect_only"):
        if mode != "hardware" or not _enabled(context, "start_linkerhand"):
            raise RuntimeError(
                "linkerhand_connect_only requires mode:=hardware and start_linkerhand:=true"
            )
    return []


def _hardware_stack(context):
    if LaunchConfiguration("mode").perform(context) != "hardware":
        return [LogInfo(msg="dual Quest dry-run: RM drivers and rm_control are not started")]

    actions = []
    if _enabled(context, "start_drivers"):
        driver_share = Path(get_package_share_directory("rm_driver"))
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                str(driver_share / "launch" / "rm_65_dual_driver.launch.py")
            )
        ))
    if _enabled(context, "start_controls"):
        control_share = Path(get_package_share_directory("rm_control"))
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                str(control_share / "launch" / "rm_65_dual_control.launch.py")
            )
        ))
    if not actions:
        actions.append(LogInfo(msg="dual Quest hardware mode: RM driver/control startup disabled"))
    return actions


def generate_launch_description():
    package_share = Path(get_package_share_directory("rm65_teleop_adapter"))
    right_launch = package_share / "launch" / "right_quest_teleop.launch.py"
    left_launch = package_share / "launch" / "left_quest_teleop.launch.py"

    return LaunchDescription([
        DeclareLaunchArgument(
            "mode", default_value="dry_run",
            description="Both adapters run in dry_run or hardware mode",
        ),
        DeclareLaunchArgument(
            "motion_profile", default_value="safe",
            description="Shared dual-arm profile: safe or normal",
        ),
        DeclareLaunchArgument(
            "start_drivers", default_value="true",
            description="Start rm_65_dual_driver.launch.py in hardware mode",
        ),
        DeclareLaunchArgument(
            "start_controls", default_value="true",
            description="Start rm_65_dual_control.launch.py in hardware mode",
        ),
        DeclareLaunchArgument(
            "start_tcp", default_value="true",
            description="Start exactly one ROS TCP endpoint for both Quest hands",
        ),
        DeclareLaunchArgument(
            "start_bridges", default_value="true",
            description="Start both Quest target bridges",
        ),
        DeclareLaunchArgument(
            "start_status", default_value="true",
            description="Start both read-only teleop status monitors",
        ),
        DeclareLaunchArgument(
            "start_linkerhand", default_value="false",
            description=(
                "Start right O7/L7 tool-RS485 control; explicit opt-in while "
                "RM driver coexistence remains under hardware investigation"
            ),
        ),
        DeclareLaunchArgument(
            "linkerhand_connect_only", default_value="false",
            description="Connect/poll the right O7 hand without writing positions",
        ),
        DeclareLaunchArgument("use_right_rviz", default_value="false"),
        DeclareLaunchArgument("use_left_rviz", default_value="false"),
        OpaqueFunction(function=_validate_arguments),
        OpaqueFunction(function=_hardware_stack),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(right_launch)),
            launch_arguments={
                "mode": LaunchConfiguration("mode"),
                "motion_profile": LaunchConfiguration("motion_profile"),
                "start_rm_driver": "false",
                "start_tcp": LaunchConfiguration("start_tcp"),
                "start_bridge": LaunchConfiguration("start_bridges"),
                "start_status": LaunchConfiguration("start_status"),
                "start_linkerhand": LaunchConfiguration("start_linkerhand"),
                "linkerhand_connect_only": LaunchConfiguration("linkerhand_connect_only"),
                "use_rviz": LaunchConfiguration("use_right_rviz"),
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(left_launch)),
            launch_arguments={
                "mode": LaunchConfiguration("mode"),
                "motion_profile": LaunchConfiguration("motion_profile"),
                "start_rm_driver": "false",
                "start_tcp": "false",
                "start_bridge": LaunchConfiguration("start_bridges"),
                "start_status": LaunchConfiguration("start_status"),
                "use_rviz": LaunchConfiguration("use_left_rviz"),
            }.items(),
        ),
    ])
