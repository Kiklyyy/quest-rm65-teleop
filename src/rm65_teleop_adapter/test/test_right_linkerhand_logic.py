import importlib.util
from pathlib import Path

import pytest


LOGIC_PATH = Path(__file__).parents[1] / "scripts" / "right_linkerhand_logic.py"


def load_logic():
    assert LOGIC_PATH.exists(), "right LinkerHand mapping has not been implemented"
    spec = importlib.util.spec_from_file_location("right_linkerhand_logic", LOGIC_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("press,expected", [
    (0.0, [255, 0, 255, 255, 255, 255, 255]),
    (1.0, [0, 0, 0, 0, 0, 0, 255]),
    (0.5, [128, 0, 128, 128, 128, 128, 255]),
    (-0.2, [255, 0, 255, 255, 255, 255, 255]),
    (1.2, [0, 0, 0, 0, 0, 0, 255]),
    (float("nan"), [255, 0, 255, 255, 255, 255, 255]),
    (float("inf"), [255, 0, 255, 255, 255, 255, 255]),
    (-float("inf"), [255, 0, 255, 255, 255, 255, 255]),
])
def test_press_index_to_l7_pose(press, expected):
    assert load_logic().target_pose(press) == expected


def test_fixed_axes_never_change():
    logic = load_logic()
    for press in (0.0, 0.1, 0.37, 0.9, 1.0):
        target = logic.target_pose(press)
        assert len(target) == 7
        assert target[1] == 0
        assert target[6] == 255
        assert all(isinstance(value, int) and 0 <= value <= 255 for value in target)
