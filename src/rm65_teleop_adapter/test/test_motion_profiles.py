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


def load_yaml_parameters(path: Path):
    with path.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    return document["rm65_teleop_adapter"]["ros__parameters"]


def test_base_configs_define_exact_orientation_envelope():
    expected = {
        "rotation_scale": 1.0,
        "max_angular_velocity_rad_s": 1.5707963267948966,
        "max_angular_step_rad": 0.01,
        "max_anchor_angle_rad": 1.5707963267948966,
        "unexpected_orientation_jump_rad": 0.7853981633974483,
    }
    for config_name in ("dry_run.yaml", "hardware.yaml"):
        params = load_yaml_parameters(PACKAGE_ROOT / "config" / config_name)
        for key, value in expected.items():
            assert params[key] == pytest.approx(value, abs=1.0e-12)


def test_home_is_hardware_only_and_uses_confirmed_configuration():
    hardware = load_yaml_parameters(PACKAGE_ROOT / "config" / "hardware.yaml")
    dry_run = load_yaml_parameters(PACKAGE_ROOT / "config" / "dry_run.yaml")
    assert dry_run["home_enabled"] is False
    assert hardware["home_enabled"] is True
    assert hardware["home_button_field"] == "upper"
    assert hardware["home_hold_seconds"] == 1.5
    assert hardware["home_speed_deg_s"] == 15.0
    assert hardware["home_joint_degrees"] == [68.3241063822369, -8.489398369548377, 60.14265142722264, 31.52005176840807, 51.634258495569824, -144.10081659391062]
    assert hardware["home_joint_names"] == [f"joint{i}" for i in range(1, 7)]
    assert hardware["home_action_name"] == "/right/rm_group_controller/follow_joint_trajectory"
    for profile in ("safe", "normal", "fast"):
        assert not (set(load_yaml_parameters(PROFILE_DIR / f"{profile}.yaml")) &
                    {"home_enabled", "home_button_field", "home_hold_seconds", "home_speed_deg_s",
                     "home_joint_degrees", "home_joint_names", "home_action_name"})
