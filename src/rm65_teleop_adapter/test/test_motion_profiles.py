import importlib.util
from pathlib import Path

import pytest
import yaml
from launch import LaunchContext
from launch.actions import DeclareLaunchArgument


PACKAGE_ROOT = Path(__file__).parents[1]
LAUNCH_PATH = PACKAGE_ROOT / "launch" / "right_quest_teleop.launch.py"
PROFILE_DIR = PACKAGE_ROOT / "config" / "motion_profiles"
ALLOWED_PROFILE_KEYS = {
    "translation_scale",
    "max_velocity_mps",
    "max_step_m",
    "max_anchor_distance_m",
}
EXPECTED_PROFILES = {
    "safe": {
        "translation_scale": 0.2,
        "max_velocity_mps": 0.005,
        "max_step_m": 0.00005,
        "max_anchor_distance_m": 0.03,
    },
    "normal": {
        "translation_scale": 1.0,
        "max_velocity_mps": 0.20,
        "max_step_m": 0.00050,
        "max_anchor_distance_m": 1.0,
    },
    "fast": {
        "translation_scale": 0.5,
        "max_velocity_mps": 0.040,
        "max_step_m": 0.00020,
        "max_anchor_distance_m": 0.10,
    },
}


def load_launch_module():
    spec = importlib.util.spec_from_file_location(
        "right_quest_teleop_launch", LAUNCH_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context_for(mode="hardware", motion_profile="safe"):
    context = LaunchContext()
    context.launch_configurations["mode"] = mode
    context.launch_configurations["motion_profile"] = motion_profile
    context.launch_configurations["start_rm_driver"] = "false"
    return context


def default_argument_value(action):
    context = LaunchContext()
    return "".join(part.perform(context) for part in action.default_value)


def test_motion_profile_defaults_to_safe(monkeypatch):
    module = load_launch_module()
    monkeypatch.setattr(
        module, "get_package_share_directory", lambda _package: str(PACKAGE_ROOT))

    description = module.generate_launch_description()
    arguments = {
        entity.name: entity
        for entity in description.entities
        if isinstance(entity, DeclareLaunchArgument)
    }

    assert "motion_profile" in arguments
    assert default_argument_value(arguments["motion_profile"]) == "safe"


@pytest.mark.parametrize("profile", ["safe", "normal", "fast"])
def test_hardware_mode_loads_base_then_selected_profile(profile):
    module = load_launch_module()

    parameters = module._adapter_parameter_files(
        context_for(motion_profile=profile), PACKAGE_ROOT)

    assert parameters == [
        str(PACKAGE_ROOT / "config" / "hardware.yaml"),
        str(PROFILE_DIR / f"{profile}.yaml"),
    ]


def test_invalid_motion_profile_is_rejected():
    module = load_launch_module()

    with pytest.raises(RuntimeError, match="motion_profile"):
        module._validate_arguments(context_for(motion_profile="turbo"))


def test_dry_run_does_not_load_hardware_or_motion_profile_config():
    module = load_launch_module()

    parameters = module._adapter_parameter_files(
        context_for(mode="dry_run", motion_profile="fast"), PACKAGE_ROOT)

    assert parameters == [str(PACKAGE_ROOT / "config" / "dry_run.yaml")]


@pytest.mark.parametrize("profile", ["safe", "normal", "fast"])
def test_profile_contains_only_allowed_motion_parameters(profile):
    with (PROFILE_DIR / f"{profile}.yaml").open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)

    parameters = document["rm65_teleop_adapter"]["ros__parameters"]
    assert set(parameters) == ALLOWED_PROFILE_KEYS
    assert parameters == EXPECTED_PROFILES[profile]
