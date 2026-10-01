"""Contract tests for the one-command dual-arm Quest bringup."""

import importlib.util
import shutil
import socket
from pathlib import Path

import pytest
import yaml
from launch import LaunchContext
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.utilities import perform_substitutions


PACKAGE = Path(__file__).parents[1]
LAUNCH = PACKAGE / "launch" / "dual_quest_teleop.launch.py"


def load_launch():
    spec = importlib.util.spec_from_file_location("dual_quest_teleop_launch", LAUNCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context_for(mode="dry_run", profile="safe", **overrides):
    context = LaunchContext()
    context.launch_configurations.update({
        "mode": mode,
        "motion_profile": profile,
        "start_drivers": "true",
        "start_controls": "true",
        "start_tcp": "true",
        "start_bridges": "true",
        "start_status": "true",
        "start_linkerhand": "false",
        "linkerhand_connect_only": "false",
        "use_right_rviz": "false",
        "use_left_rviz": "false",
        **overrides,
    })
    return context


def default_value(action):
    return "".join(part.perform(LaunchContext()) for part in action.default_value)


def test_safe_defaults_and_single_tcp_owner(monkeypatch):
    module = load_launch()
    monkeypatch.setattr(
        module, "get_package_share_directory",
        lambda package: str(PACKAGE) if package == "rm65_teleop_adapter" else f"/tmp/{package}",
    )
    description = module.generate_launch_description()
    arguments = {
        action.name: action for action in description.entities
        if isinstance(action, DeclareLaunchArgument)
    }
    assert default_value(arguments["mode"]) == "dry_run"
    assert default_value(arguments["motion_profile"]) == "safe"
    assert default_value(arguments["start_drivers"]) == "true"
    assert default_value(arguments["start_controls"]) == "true"
    assert default_value(arguments["start_linkerhand"]) == "false"

    preflight = next(action for action in description.entities
                     if isinstance(action, OpaqueFunction))
    hardware_start = next(action for action in description.entities
                          if isinstance(action, OpaqueFunction)
                          and action is not preflight)
    assert description.entities.index(preflight) < description.entities.index(hardware_start)

    children = [action for action in description.entities
                if isinstance(action, IncludeLaunchDescription)]
    assert len(children) == 2
    right_args = dict(children[0].launch_arguments)
    left_args = dict(children[1].launch_arguments)
    context = LaunchContext()
    context.launch_configurations.update({"start_tcp": "true", "start_linkerhand": "true"})
    assert right_args["start_tcp"].perform(context) == "true"
    assert left_args["start_tcp"] == "false"
    assert right_args["start_rm_driver"] == "false"
    assert left_args["start_rm_driver"] == "false"
    assert right_args["start_linkerhand"].perform(context) == "true"
    assert "start_linkerhand" not in left_args


def test_dry_run_never_starts_rm_hardware():
    actions = load_launch()._hardware_stack(context_for())
    assert len(actions) == 1
    assert isinstance(actions[0], LogInfo)


def test_hardware_reuses_verified_dual_rm_launches(monkeypatch):
    module = load_launch()
    monkeypatch.setattr(
        module, "get_package_share_directory", lambda package: f"/opt/share/{package}")
    actions = module._hardware_stack(context_for(mode="hardware"))
    assert len(actions) == 2
    assert all(isinstance(action, IncludeLaunchDescription) for action in actions)
    locations = [perform_substitutions(
        LaunchContext(),
        action.launch_description_source._LaunchDescriptionSource__location,
    ) for action in actions]
    assert locations == [
        "/opt/share/rm_driver/launch/rm_65_dual_driver.launch.py",
        "/opt/share/rm_control/launch/rm_65_dual_control.launch.py",
    ]


@pytest.mark.parametrize("profile", ["fast", "left_test", "turbo"])
def test_dual_hardware_rejects_unshared_profiles(profile):
    with pytest.raises(RuntimeError, match="safe or normal"):
        load_launch()._validate_arguments(context_for(mode="hardware", profile=profile))


def test_connect_only_requires_explicit_hardware_hand():
    module = load_launch()
    with pytest.raises(RuntimeError, match="requires"):
        module._validate_arguments(context_for(linkerhand_connect_only="true"))
    with pytest.raises(RuntimeError, match="requires"):
        module._validate_arguments(context_for(
            mode="hardware", linkerhand_connect_only="true", start_linkerhand="false"))
    assert module._validate_arguments(context_for(
        mode="hardware", linkerhand_connect_only="true", start_linkerhand="true")) == []


def test_preflight_rejects_left_home_mismatch_before_hardware_start(tmp_path, monkeypatch):
    module = load_launch()
    share = tmp_path / "share"
    shutil.copytree(PACKAGE / "config", share / "config")
    (share / "launch").mkdir()
    shutil.copyfile(PACKAGE / "launch" / "left_quest_teleop.launch.py",
                    share / "launch" / "left_quest_teleop.launch.py")
    (share / "launch" / "right_quest_teleop.launch.py").touch()
    hardware = share / "config" / "hardware.yaml"
    data = yaml.safe_load(hardware.read_text(encoding="utf-8"))
    data["left_rm65_teleop_adapter"]["ros__parameters"]["home_speed_deg_s"] = 12.0
    hardware.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setattr(module, "get_package_share_directory", lambda _: str(share))
    monkeypatch.setattr(module, "_running_executables", lambda _: {})
    with pytest.raises(RuntimeError, match="left Home config mismatch: home_speed_deg_s"):
        module._preflight(context_for(mode="hardware", profile="normal", start_tcp="false"))


def test_preflight_rejects_existing_command_process(monkeypatch):
    module = load_launch()
    monkeypatch.setattr(module, "get_package_share_directory", lambda _: str(PACKAGE))
    monkeypatch.setattr(module, "_running_executables",
                        lambda _: {"rm_driver": [1234]})
    with pytest.raises(RuntimeError, match="rm_driver PID \\[1234\\]"):
        module._preflight(context_for(mode="hardware", start_tcp="false"))


def test_preflight_rejects_busy_tcp_port():
    module = load_launch()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("0.0.0.0", 0))
        with pytest.raises(RuntimeError, match="already in use"):
            module._check_tcp_port_free(occupied.getsockname()[1])


def test_preflight_rejects_invalid_optional_switch_before_hardware_start():
    module = load_launch()
    with pytest.raises(Exception, match="start_status|condition expression"):
        module._preflight(context_for(mode="hardware", start_status="maybe"))
