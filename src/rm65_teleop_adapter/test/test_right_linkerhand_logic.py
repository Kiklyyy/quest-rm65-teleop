import importlib.util
from pathlib import Path

import pytest

LOGIC_PATH = Path(__file__).parents[1] / "scripts" / "right_linkerhand_logic.py"


def load_logic():
    spec = importlib.util.spec_from_file_location("right_linkerhand_logic", LOGIC_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_poses_and_startup():
    module = load_logic()
    assert module.CLOSED_POSE == (73, 0, 0, 0, 0, 0, 156)
    assert module.OPEN_POSE == (73, 0, 255, 255, 255, 255, 156)
    assert len(module.CLOSED_POSE) == len(module.OPEN_POSE) == 7
    logic = module.LinkerHandToggleLogic()
    assert logic.hand_toggle_state == "OPEN"
    assert logic.trigger_armed is True
    assert logic.update(0.0) is None
    assert logic.target is None


def test_press_hold_release_repeat():
    logic = load_logic().LinkerHandToggleLogic()
    assert logic.update(0.60) == [73, 0, 0, 0, 0, 0, 156]
    assert logic.hand_toggle_state == "CLOSED"
    assert logic.update(1.0) is None
    assert logic.update(0.5) is None
    assert logic.update(0.40) is None
    assert logic.hand_toggle_state == "CLOSED"
    assert logic.update(0.60) == [73, 0, 255, 255, 255, 255, 156]
    assert logic.update(0.0) is None
    assert logic.update(1.0) == [73, 0, 0, 0, 0, 0, 156]


def test_hysteresis_band_does_not_create_edges():
    logic = load_logic().LinkerHandToggleLogic()
    assert logic.update(0.59) is None
    assert logic.trigger_pressed is False
    assert logic.update(0.60) is not None
    for value in (0.59, 0.50, 0.41, 0.59, 0.60):
        assert logic.update(value) is None
    assert logic.trigger_pressed is True
    assert logic.update(0.40) is None
    assert logic.trigger_pressed is False
    assert logic.update(0.59) is None
    assert logic.update(0.60) == list(load_logic().OPEN_POSE)


@pytest.mark.parametrize("initial_press", [False, True])
def test_stale_reconnect_requires_valid_release(initial_press):
    logic = load_logic().LinkerHandToggleLogic()
    if initial_press:
        assert logic.update(1.0) == list(load_logic().CLOSED_POSE)
    else:
        assert logic.update(0.0) is None
    state = logic.hand_toggle_state
    logic.input_lost()
    assert logic.trigger_armed is False
    assert logic.trigger_value is None
    assert logic.update(1.0) is None
    assert logic.hand_toggle_state == state
    assert logic.update(0.5) is None
    assert logic.trigger_armed is False
    assert logic.update(0.4) is None
    assert logic.trigger_armed is True
    expected = load_logic().OPEN_POSE if initial_press else load_logic().CLOSED_POSE
    assert logic.update(0.6) == list(expected)
    assert logic.update(1.0) is None


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_disarms_without_motion(invalid):
    logic = load_logic().LinkerHandToggleLogic()
    assert logic.update(invalid) is None
    assert logic.trigger_value is None
    assert logic.trigger_armed is False
    assert logic.update(1.0) is None
    assert logic.update(0.4) is None
    assert logic.update(0.6) == list(load_logic().CLOSED_POSE)


def test_bad_thresholds_rejected():
    module = load_logic()
    with pytest.raises(ValueError):
        module.LinkerHandToggleLogic(press_threshold=0.4, release_threshold=0.6)
