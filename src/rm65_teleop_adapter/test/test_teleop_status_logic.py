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
        "button_lower": False,
        "command_path_ready": True,
        "reason": "",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_initial_status_reports_missing_inputs_without_crashing():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)

    assert model.render(now_s=0.0) == (
        "[teleop] QUEST=LOST INPUTS=LOST TARGET=LOST ROBOT=LOST "
        "STATE=UNKNOWN DEADMAN=? CMD=UNKNOWN"
    )


def test_live_streams_and_adapter_status_render_one_line_summary():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    for stream in ("quest", "inputs", "target", "robot"):
        model.mark_stream(stream, now_s=1.0)
    model.update_adapter(adapter_payload(), now_s=1.0)

    assert model.render(now_s=1.1) == (
        "[teleop] QUEST=OK INPUTS=OK TARGET=OK ROBOT=OK "
        "STATE=ARMED DEADMAN=OFF CMD=OK"
    )


def test_each_stream_has_independent_display_freshness():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.mark_stream("target", now_s=1.0)
    model.mark_stream("robot", now_s=1.0)
    model.update_adapter(
        adapter_payload(state="REARM_REQUIRED", button_lower=True), now_s=1.0)

    assert model.render(now_s=1.1) == (
        "[teleop] QUEST=LOST INPUTS=LOST TARGET=OK ROBOT=OK "
        "STATE=REARM_REQUIRED DEADMAN=ON CMD=OK"
    )


def test_malformed_adapter_json_becomes_unknown():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.update_adapter("{not-json", now_s=1.0)

    assert model.render(now_s=1.1).endswith(
        "STATE=UNKNOWN DEADMAN=? CMD=UNKNOWN"
    )


def test_stale_adapter_status_becomes_unknown():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.update_adapter(adapter_payload(state="ACTIVE", button_lower=True), now_s=1.0)

    assert model.render(now_s=1.6).endswith(
        "STATE=UNKNOWN DEADMAN=? CMD=UNKNOWN"
    )


def test_fault_reason_is_compacted_for_single_line_output():
    logic = load_logic_module()
    model = logic.TeleopStatusModel(stream_timeout_s=0.5, adapter_timeout_s=0.5)
    model.update_adapter(
        adapter_payload(state="FAULT", reason="control period exceeded"), now_s=1.0)

    assert model.render(now_s=1.1).endswith(
        "STATE=FAULT DEADMAN=OFF CMD=OK REASON=control_period_exceeded"
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
