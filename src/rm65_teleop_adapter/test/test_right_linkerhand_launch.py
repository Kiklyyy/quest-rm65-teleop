"""The hand is opt-in and follows the right launch's dry-run/hardware mode."""

import importlib.util
from pathlib import Path

from launch import LaunchContext
from launch.actions import DeclareLaunchArgument, OpaqueFunction


LAUNCH = Path(__file__).parents[1] / "launch" / "right_quest_teleop.launch.py"


def load_launch():
    spec = importlib.util.spec_from_file_location("right_quest_teleop_launch", LAUNCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hand_start_is_explicit_and_defaults_off():
    description = load_launch().generate_launch_description()
    args = {action.name: action for action in description.entities
            if isinstance(action, DeclareLaunchArgument)}
    assert "start_linkerhand" in args
    assert "linkerhand_connect_only" in args
    assert "".join(part.perform(LaunchContext())
                   for part in args["linkerhand_connect_only"].default_value) == "false"
    assert "".join(part.perform(LaunchContext())
                   for part in args["start_linkerhand"].default_value) == "false"
    assert any(isinstance(action, OpaqueFunction)
               and action._OpaqueFunction__function.__name__ == "_linkerhand_node"
               and action._Action__condition is not None
               for action in description.entities)


def test_hand_mode_cannot_enable_sdk_in_dry_run():
    module = load_launch()
    context = LaunchContext()
    context.launch_configurations["mode"] = "dry_run"
    context.launch_configurations["linkerhand_connect_only"] = "false"
    assert module._linkerhand_parameters(context) == {
        "dry_run": True, "hardware_write_enabled": False, "connect_only": False,
    }
    context.launch_configurations["mode"] = "hardware"
    assert module._linkerhand_parameters(context) == {
        "dry_run": False, "hardware_write_enabled": True, "connect_only": False,
    }
    context.launch_configurations["linkerhand_connect_only"] = "true"
    assert module._linkerhand_parameters(context)["connect_only"] is True
    context.launch_configurations["mode"] = "dry_run"
    try:
        module._linkerhand_parameters(context)
    except RuntimeError as exc:
        assert "connect_only" in str(exc)
    else:
        raise AssertionError("dry-run must reject connect_only")
