import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "teleop_status_logic.py"


def load_logic_module():
    if not MODULE_PATH.exists():
        raise AssertionError("teleop status logic module has not been implemented")
    spec = importlib.util.spec_from_file_location("teleop_status_logic", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def adapter_payload(**overrides):
    payload = {
        "state": "ARMED",
        "deadman_pressed": False,
        "deadman_source": "press_middle",
        "command_path_ready": True,
        "reason": "",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_initial_status_reports_missing_inputs_without_crashing():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)

    assert model.render(now_s=0.0) == (
        "[teleop] QUEST=LOST INPUTS=LOST TARGET=LOST ROBOT=LOST JOINTS=LOST "
        "STATE=UNKNOWN DEADMAN=? CMD=UNKNOWN HOME=IDLE"
    )


def test_live_streams_and_adapter_status_render_one_line_summary():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    for stream in ("quest", "inputs", "target", "robot"):
        model.mark_stream(stream, now_s=1.0)
    model.update_adapter(adapter_payload(), now_s=1.0)

    assert model.render(now_s=1.1) == (
        "[teleop] QUEST=OK INPUTS=OK TARGET=OK ROBOT=OK JOINTS=LOST "
        "STATE=ARMED DEADMAN=OFF CMD=OK HOME=IDLE"
    )


def test_each_stream_has_independent_display_freshness():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.mark_stream("target", now_s=1.0)
    model.mark_stream("robot", now_s=1.0)
    model.update_adapter(
        adapter_payload(state="REARM_REQUIRED", deadman_pressed=True), now_s=1.0)

    assert model.render(now_s=1.1) == (
        "[teleop] QUEST=LOST INPUTS=LOST TARGET=OK ROBOT=OK JOINTS=LOST "
        "STATE=REARM_REQUIRED DEADMAN=ON CMD=OK HOME=IDLE"
    )


def test_malformed_adapter_json_becomes_unknown():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.update_adapter("{not-json", now_s=1.0)

    assert model.render(now_s=1.1).endswith(
        "STATE=UNKNOWN DEADMAN=? CMD=UNKNOWN HOME=IDLE"
    )


def test_stale_adapter_status_becomes_unknown():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.update_adapter(
        adapter_payload(state="ACTIVE", deadman_pressed=True), now_s=1.0)

    assert model.render(now_s=1.6).endswith(
        "STATE=UNKNOWN DEADMAN=? CMD=UNKNOWN HOME=IDLE"
    )


def test_fault_reason_is_compacted_for_single_line_output():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.update_adapter(
        adapter_payload(state="FAULT", reason="control period exceeded"), now_s=1.0)

    assert model.render(now_s=1.1).endswith(
        "STATE=FAULT DEADMAN=OFF CMD=OK HOME=IDLE REASON=control_period_exceeded"
    )


def test_output_is_immediate_on_change_then_heartbeat_limited():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(
        stream_timeout_s=0.5,
        adapter_timeout_s=0.5,
        heartbeat_s=1.0,
    )

    assert model.take_line_if_due(now_s=0.0) is not None
    assert model.take_line_if_due(now_s=0.1) is None

    model.mark_stream("quest", now_s=0.2)
    assert model.take_line_if_due(now_s=0.2) is not None
    assert model.take_line_if_due(now_s=0.9) is not None
    assert model.take_line_if_due(now_s=1.0) is None
    assert model.take_line_if_due(now_s=1.91) is not None


def test_unknown_stream_name_is_rejected():
    logic = load_logic_module()
    model = logic.TeleopStatusModel()

    try:
        model.mark_stream("typo", now_s=0.0)
    except ValueError as error:
        assert "typo" in str(error)
    else:
        raise AssertionError("unknown stream name should be rejected")


def test_semantic_deadman_field_takes_precedence_over_legacy_button_lower():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.update_adapter(
        adapter_payload(deadman_pressed=False, button_lower=True), now_s=1.0)

    assert model.render(now_s=1.1).endswith(
        "STATE=ARMED DEADMAN=OFF CMD=OK HOME=IDLE"
    )


def test_legacy_button_lower_is_supported_as_fallback():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    legacy = adapter_payload(button_lower=True)
    legacy = json.loads(legacy)
    legacy.pop("deadman_pressed")
    legacy.pop("deadman_source")
    model.update_adapter(json.dumps(legacy), now_s=1.0)

    assert model.render(now_s=1.1).endswith(
        "STATE=ARMED DEADMAN=ON CMD=OK HOME=IDLE"
    )


def test_joint_stream_reports_lost_then_ok():
    model = load_logic_module().TeleopStatusModel()
    assert "JOINTS=LOST" in model.render(0.0)
    model.mark_stream("joints", 1.0)
    assert "JOINTS=OK" in model.render(1.1)


def test_homing_and_hold_progress_are_visible():
    model = load_logic_module().TeleopStatusModel()
    model.update_adapter(adapter_payload(state="HOMING", home_action_state="ACTIVE"), 1.0)
    assert "HOME=ACTIVE" in model.render(1.1)
    model.update_adapter(adapter_payload(home_button_pressed=True, home_hold_progress=0.5), 2.0)
    assert "HOME=HOLD(50%)" in model.render(2.1)


def test_malformed_home_fields_fall_back_safely():
    model = load_logic_module().TeleopStatusModel()
    model.update_adapter(adapter_payload(home_button_pressed="true", home_hold_progress="nan"), 1.0)
    assert "HOME=IDLE" in model.render(1.1)
    model.update_adapter("{broken", 2.0)
    assert "HOME=IDLE" in model.render(2.1)
