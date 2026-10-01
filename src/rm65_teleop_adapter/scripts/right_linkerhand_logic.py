"""Pure rising-edge toggle logic for the right LinkerHand L7."""

import math

# Canonical O7 order: Thumb_Pitch, Thumb_Yaw, Index_Pitch, Middle_Pitch,
# Ring_Pitch, Little_Pitch, Thumb_Roll.
CLOSED_POSE = (73, 0, 0, 0, 0, 0, 156)
OPEN_POSE = (73, 0, 255, 255, 255, 255, 156)


class LinkerHandToggleLogic:
    """One command per armed RELEASED-to-PRESSED transition."""

    def __init__(self, press_threshold=0.60, release_threshold=0.40):
        if not (math.isfinite(press_threshold) and math.isfinite(release_threshold)
                and 0.0 <= release_threshold < press_threshold <= 1.0):
            raise ValueError("require 0 <= release_threshold < press_threshold <= 1")
        self.press_threshold = press_threshold
        self.release_threshold = release_threshold
        self.hand_toggle_state = "OPEN"
        self.target = None
        self.trigger_value = None
        self.trigger_pressed = False
        self.trigger_armed = True

    def input_lost(self):
        """Hold the hand and require a valid released sample before rearming."""
        self.trigger_value = None
        self.trigger_armed = False
        # Clear semantic press so a reconnect still needs a valid release.
        self.trigger_pressed = False

    def update(self, press_index):
        """Return a new seven-axis target, or None when no write is needed."""
        value = float(press_index)
        if not math.isfinite(value):
            self.input_lost()
            return None
        self.trigger_value = value
        was_pressed = self.trigger_pressed
        # Quest message field is float32; allow its rounding at exact thresholds.
        if value >= self.press_threshold - 1e-6:
            self.trigger_pressed = True
        elif value <= self.release_threshold + 1e-6:
            self.trigger_pressed = False
            self.trigger_armed = True
        if self.trigger_pressed and not was_pressed and self.trigger_armed:
            self.trigger_armed = False
            self.hand_toggle_state = (
                "CLOSED" if self.hand_toggle_state == "OPEN" else "OPEN")
            self.target = list(
                CLOSED_POSE if self.hand_toggle_state == "CLOSED" else OPEN_POSE)
            return list(self.target)
        return None
