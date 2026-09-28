"""Quest index trigger to right LinkerHand L7 joint targets."""

import math


OPEN_POSE = (255, 0, 255, 255, 255, 255, 255)
CLOSE_POSE = (0, 0, 0, 0, 0, 0, 255)


def target_pose(press_index):
    """Return seven integer targets; non-finite input releases the hand."""
    press = float(press_index)
    if not math.isfinite(press):
        press = 0.0
    press = min(1.0, max(0.0, press))
    return [round(opened + press * (closed - opened))
            for opened, closed in zip(OPEN_POSE, CLOSE_POSE)]
