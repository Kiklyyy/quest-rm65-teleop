"""Left/right endpoint isolation and explicit left hardware launch gates."""

import importlib.util
from pathlib import Path

import pytest
import yaml
from launch import LaunchContext


PACKAGE = Path(__file__).parents[1]


def params(name, node):
    document = yaml.safe_load((PACKAGE / "config" / name).read_text(encoding="utf-8"))
    common = document.get("/**", {}).get("ros__parameters", {})
    return {**common, **document[node]["ros__parameters"]}


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


def test_right_home_config_and_profile_remain_unchanged():
    right = params("hardware.yaml", "rm65_teleop_adapter")
    normal = params("motion_profiles/normal.yaml", "rm65_teleop_adapter")
    assert right["expected_driver_node"] == "/right/rm_driver"
    assert right["home_enabled"] is True
    assert right["home_button_field"] == "upper"
    assert right["home_hold_seconds"] == 1.5
    assert right["home_speed_deg_s"] == 15.0
    assert right["home_action_name"] == "/right/rm_group_controller/follow_joint_trajectory"
    assert right["home_joint_degrees"] == [
        68.3241063822369, -8.489398369548377, 60.14265142722264,
        31.52005176840807, 51.634258495569824, -144.10081659391062]
    assert normal == {
        "translation_scale": 1.0, "max_velocity_mps": 0.20,
        "max_step_m": 0.00050, "max_anchor_distance_m": 1.0,
    }


def test_left_hardware_home_is_independent_and_normal_overlay_isolated():
    module = left_launch_module()
    left = params("hardware.yaml", "left_rm65_teleop_adapter")
    right = params("hardware.yaml", "rm65_teleop_adapter")
    assert left["expected_driver_node"] == "/left/rm_driver"
    assert left["expected_adapter_node"] == "/left_rm65_teleop_adapter"
    assert left["mapping"] == [0, 0, -1, -1, 0, 0, 0, 1, 0]
    assert left["home_enabled"] is True
    assert left["home_button_field"] == "upper"  # Quest physical Y, not X/lower.
    assert left["home_hold_seconds"] == 1.5
    assert left["home_speed_deg_s"] == 15.0
    assert left["home_joint_names"] == [f"joint{i}" for i in range(1, 7)]
    assert left["home_joint_degrees"] == [
        -90.52991560598026, -7.43359734865227, -62.41522144150158,
        -3.5143370089334374, -37.08400247904573, 99.21228312734117]
    assert left["home_action_name"] == "/left/rm_group_controller/follow_joint_trajectory"
    assert left["home_joint_degrees"] != right["home_joint_degrees"]
    assert left["home_action_name"] != right["home_action_name"]
    assert left["home_movej_topic"] == "/left/rm_driver/movej_canfd_cmd"
    assert left["stop_topic"] == "/left/rm_driver/move_stop_cmd"
    assert left["workspace_min"] == [-1, -1, 0]
    assert left["workspace_max"] == [1, 1, 1.5]
    files = module._adapter_parameter_files(context_for("hardware", "normal"), PACKAGE)
    assert files == [str(PACKAGE / "config" / "hardware.yaml"),
                     params("motion_profiles/normal.yaml", "rm65_teleop_adapter")]


def test_single_hardware_file_deduplicates_shared_parameters():
    config_path = PACKAGE / "config" / "hardware.yaml"
    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    common = document["/**"]["ros__parameters"]
    right = document["rm65_teleop_adapter"]["ros__parameters"]
    left = document["left_rm65_teleop_adapter"]["ros__parameters"]

    assert not (PACKAGE / "config" / "left_hardware.yaml").exists()
    assert set(common).isdisjoint(right)
    assert set(common).isdisjoint(left)
    assert set(right) == set(left)
    assert common["dry_run"] is False
    assert common["workspace_min"] == [-1, -1, 0]
    assert common["workspace_max"] == [1, 1, 1.5]


def test_dry_run_remains_default_and_left_test_is_retired():
    module = left_launch_module()
    dry_run = params("left_dry_run.yaml", "left_rm65_teleop_adapter")
    assert dry_run["home_enabled"] is False
    assert "home_action_name" not in dry_run
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
    left_path = tmp_path / "config" / "hardware.yaml"
    document = yaml.safe_load(left_path.read_text(encoding="utf-8"))
    left = document["left_rm65_teleop_adapter"]["ros__parameters"]

    def write():
        left_path.write_text(yaml.safe_dump(document), encoding="utf-8")

    left["expected_driver_node"] = "/right/rm_driver"
    write()
    with pytest.raises(RuntimeError, match="endpoint mismatch"):
        module._validate_hardware_config(left_path, tmp_path)
    left["expected_driver_node"] = "/left/rm_driver"
    left["inputs_timeout"] = 1.0
    write()
    with pytest.raises(RuntimeError, match="safety mismatch: inputs_timeout"):
        module._validate_hardware_config(left_path, tmp_path)
    del left["inputs_timeout"]
    left["home_action_name"] = "/right/rm_group_controller/follow_joint_trajectory"
    write()
    with pytest.raises(RuntimeError, match="Home config mismatch: home_action_name"):
        module._validate_hardware_config(left_path, tmp_path)
    left["home_action_name"] = "/left/rm_group_controller/follow_joint_trajectory"
    left["home_button_field"] = "lower"
    write()
    with pytest.raises(RuntimeError, match="Home config mismatch: home_button_field"):
        module._validate_hardware_config(left_path, tmp_path)
    left["home_button_field"] = "upper"
    left["home_joint_degrees"][0] = float("nan")
    write()
    with pytest.raises(RuntimeError, match="six finite degrees"):
        module._validate_hardware_config(left_path, tmp_path)
