"""Left/right endpoint isolation and explicit left hardware launch gates."""

import importlib.util
from pathlib import Path

import pytest
import yaml
from launch import LaunchContext


PACKAGE = Path(__file__).parents[1]


def params(name, node):
    document = yaml.safe_load((PACKAGE / "config" / name).read_text(encoding="utf-8"))
    return document[node]["ros__parameters"]


def left_launch_module():
    path = PACKAGE / "launch" / "left_quest_teleop.launch.py"
    spec = importlib.util.spec_from_file_location("left_quest_teleop_launch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context_for(mode="dry_run", profile="safe", start_driver="false"):
    context = LaunchContext()
    context.launch_configurations.update({
        "mode": mode, "motion_profile": profile, "start_rm_driver": start_driver,
    })
    return context


def test_right_config_and_profile_remain_separate():
    right = params("hardware.yaml", "rm65_teleop_adapter")
    normal = params("motion_profiles/normal.yaml", "rm65_teleop_adapter")
    assert right["expected_driver_node"] == "/right/rm_driver"
    assert right["home_enabled"] is True
    assert normal == {
        "translation_scale": 1.0, "max_velocity_mps": 0.20,
        "max_step_m": 0.00050, "max_anchor_distance_m": 1.0,
    }


def test_left_hardware_gate_normal_overlay_and_home_isolation():
    module = left_launch_module()
    left = params("left_hardware.yaml", "left_rm65_teleop_adapter")
    assert left["expected_driver_node"] == "/left/rm_driver"
    assert left["expected_adapter_node"] == "/left_rm65_teleop_adapter"
    assert left["mapping"] == [0, 0, -1, -1, 0, 0, 0, 1, 0]
    assert left["home_enabled"] is False
    assert not any(key in left for key in (
        "home_action_name", "home_joint_degrees", "home_joint_names",
        "home_button_field", "home_hold_seconds", "home_speed_deg_s"))
    assert left["workspace_min"] == [-1, -1, 0]
    assert left["workspace_max"] == [1, 1, 1.5]
    files = module._adapter_parameter_files(context_for("hardware", "normal"), PACKAGE)
    assert files == [str(PACKAGE / "config" / "left_hardware.yaml"),
                     params("motion_profiles/normal.yaml", "rm65_teleop_adapter")]


def test_dry_run_remains_default_and_left_test_is_retired():
    module = left_launch_module()
    assert module._adapter_parameter_files(context_for(), PACKAGE) == [
        str(PACKAGE / "config" / "left_dry_run.yaml")]
    with pytest.raises(RuntimeError, match="safe or normal"):
        module._validate_arguments(context_for("hardware", "left_test"))
    with pytest.raises(RuntimeError, match="driver separately"):
        module._validate_arguments(context_for(start_driver="true"))


def test_left_hardware_rejects_wrong_owner_or_weakened_safety(tmp_path):
    module = left_launch_module()
    (tmp_path / "config" / "motion_profiles").mkdir(parents=True)
    for name in ("hardware.yaml", "motion_profiles/safe.yaml"):
        source = PACKAGE / "config" / name
        (tmp_path / "config" / name).write_bytes(source.read_bytes())
    left = params("left_hardware.yaml", "left_rm65_teleop_adapter")
    left_path = tmp_path / "config" / "left_hardware.yaml"

    def write():
        left_path.write_text(yaml.safe_dump({"left_rm65_teleop_adapter": {
            "ros__parameters": left}}), encoding="utf-8")

    left["expected_driver_node"] = "/right/rm_driver"
    write()
    with pytest.raises(RuntimeError, match="endpoint mismatch"):
        module._validate_hardware_config(left_path, tmp_path)
    left["expected_driver_node"] = "/left/rm_driver"
    left["inputs_timeout"] = 1.0
    write()
    with pytest.raises(RuntimeError, match="safety mismatch: inputs_timeout"):
        module._validate_hardware_config(left_path, tmp_path)
    left["inputs_timeout"] = 0.20
    left["home_action_name"] = "/left/unsafe"
    write()
    with pytest.raises(RuntimeError, match="Home must remain unconfigured"):
        module._validate_hardware_config(left_path, tmp_path)
