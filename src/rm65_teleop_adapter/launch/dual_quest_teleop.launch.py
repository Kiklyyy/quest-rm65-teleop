"""Bring up both RM65 arms, both Quest adapters, and optional right O7 hand."""

import importlib.util
import os
import socket
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


def _running_executables(names):
    """Find existing hardware command processes before creating another stack."""
    found = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            executable = os.readlink(f"/proc/{entry.name}/exe")
        except OSError:  # A process may exit or be inaccessible while scanning.
            continue
        name = os.path.basename(executable).removesuffix(" (deleted)")
        if name in names:
            found.setdefault(name, []).append(int(entry.name))
    return found


def _check_tcp_port_free(port=10000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("0.0.0.0", port))
        except OSError as exc:
            raise RuntimeError(
                f"ROS TCP port {port} is already in use; stop the existing endpoint "
                "before starting another dual Quest stack"
            ) from exc


def _preflight(context):
    """Validate the complete stack before any driver, TCP, or adapter starts."""
    _validate_arguments(context)
    for name in (
        "start_drivers", "start_controls", "start_tcp", "start_bridges",
        "start_status", "start_linkerhand", "linkerhand_connect_only",
        "use_right_rviz", "use_left_rviz",
    ):
        _enabled(context, name)
    package_share = Path(get_package_share_directory("rm65_teleop_adapter"))
    for child in ("right_quest_teleop.launch.py", "left_quest_teleop.launch.py"):
        if not (package_share / "launch" / child).is_file():
            raise RuntimeError(f"missing dual Quest child launch: {child}")

    names = {"rm65_teleop_adapter_node"}
    if LaunchConfiguration("mode").perform(context) == "hardware":
        left_launch = package_share / "launch" / "left_quest_teleop.launch.py"
        spec = importlib.util.spec_from_file_location("left_quest_preflight", left_launch)
        left = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(left)
        left._validate_hardware_config(package_share / "config" / "hardware.yaml", package_share)
        if LaunchConfiguration("motion_profile").perform(context) == "normal":
            left._normal_overlay(package_share)
        if _enabled(context, "start_drivers"):
            names.add("rm_driver")
        if _enabled(context, "start_controls"):
            names.add("rm_control")
    else:
        for name in ("dry_run.yaml", "left_dry_run.yaml"):
            if not (package_share / "config" / name).is_file():
                raise RuntimeError(f"missing dual Quest dry-run config: {name}")

    existing = _running_executables(names)
    if existing:
        details = ", ".join(f"{name} PID {pids}" for name, pids in sorted(existing.items()))
        raise RuntimeError(f"dual Quest command process already running: {details}")
    if _enabled(context, "start_tcp"):
        _check_tcp_port_free()
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
        OpaqueFunction(function=_preflight),
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
