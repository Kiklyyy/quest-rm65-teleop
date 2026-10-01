#!/usr/bin/env python3
"""Independent Quest index-trigger controller for the right LinkerHand L7."""

import json
import math
from pathlib import Path
import sys
import time

import rclpy
from quest2ros.msg import OVR2ROSInputs
from rclpy.node import Node
from std_msgs.msg import String

from right_linkerhand_logic import LinkerHandToggleLogic


DEFAULT_SDK_PATH = "/home/lh/quest2ros2_ws/linkerhand/linker_hand_python_sdk"


def load_hand_factory(sdk_path):
    root = Path(sdk_path)
    if not (root / "LinkerHand" / "core" / "rs485" / "realman_modbus.py").is_file():
        raise RuntimeError(f"RealMan-adapted LinkerHand SDK not found at {root}")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from LinkerHand.linker_hand_api import LinkerHandApi
    return LinkerHandApi


def seven_readings(values, field):
    if values is None or len(values) != 7:
        raise ValueError(f"{field} must contain seven readings")
    result = [int(value) for value in values]
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError(f"{field} contains a non-finite value")
    return result


class RightLinkerHandNode(Node):
    def __init__(self, *, hand_factory=None, parameter_overrides=None):
        super().__init__("right_linkerhand", parameter_overrides=parameter_overrides)
        self._dry_run = self.declare_parameter("dry_run", True).value
        write_enabled = self.declare_parameter("hardware_write_enabled", False).value
        self._connect_only = bool(self.declare_parameter("connect_only", False).value)
        if bool(self._dry_run) == bool(write_enabled):
            raise ValueError(
                "dry_run and hardware_write_enabled must be opposite; "
                "hardware write requires dry_run=false and hardware_write_enabled=true")
        if self._connect_only and self._dry_run:
            raise ValueError("connect_only requires hardware mode to initialize the SDK")

        sdk_path = self.declare_parameter("sdk_path", DEFAULT_SDK_PATH).value
        inputs_topic = self.declare_parameter(
            "inputs_topic", "/q2r_right_hand_inputs").value
        status_topic = self.declare_parameter(
            "status_topic", "/right/linkerhand/status").value
        send_rate_hz = float(self.declare_parameter("send_rate_hz", 20.0).value)
        feedback_rate_hz = float(self.declare_parameter("feedback_rate_hz", 2.0).value)
        status_rate_hz = float(self.declare_parameter("status_rate_hz", 10.0).value)
        self._input_timeout_s = float(self.declare_parameter("input_timeout_s", 0.5).value)
        if (not inputs_topic or not status_topic or
                any(not math.isfinite(rate) or rate <= 0.0
                    for rate in (send_rate_hz, feedback_rate_hz, status_rate_hz,
                                 self._input_timeout_s))):
            raise ValueError("LinkerHand topics and rates/timeouts must be valid")

        self._toggle = LinkerHandToggleLogic()
        self._target = None
        self._pending_target = None
        self._actual = None
        self._fault_codes = None
        self._last_input_s = None
        self._input_stale = False
        self._invalid_input_count = 0
        self._input_error = ""
        self._communication_error = ""
        self._communication_ok = False
        self._last_warning_s = -float("inf")
        self._hand = None
        if not self._dry_run:
            try:
                factory = hand_factory or load_hand_factory(sdk_path)
                # Pin the onsite RealMan tool-RS485 transport; never fall back to CAN.
                self._hand = factory(hand_type="right", hand_joint="L7", modbus="RML")
                self._communication_ok = True
            except Exception as exc:
                raise RuntimeError(f"right LinkerHand L7 SDK connection failed: {exc}") from exc
            # Establish fault/feedback state before any Quest sample can cause a write.
            self._poll_feedback()

        self._status_pub = self.create_publisher(String, status_topic, 10)
        self._inputs_sub = self.create_subscription(
            OVR2ROSInputs, inputs_topic, self._on_inputs, 10)
        self._send_timer = self.create_timer(1.0 / send_rate_hz, self._send_target)
        if not self._dry_run:
            self._feedback_timer = self.create_timer(
                1.0 / feedback_rate_hz, self._poll_feedback)
        self._status_timer = self.create_timer(1.0 / status_rate_hz, self._publish_status)

    def _warn_limited(self, message):
        now = time.monotonic()
        if now - self._last_warning_s >= 5.0:
            self.get_logger().warning(message)
            self._last_warning_s = now

    def _on_inputs(self, message):
        if self._connect_only:
            return
        value = float(message.press_index)
        now = time.monotonic()
        if (self._last_input_s is not None and
                now - self._last_input_s > self._input_timeout_s):
            self._mark_input_lost()
        self._last_input_s = now
        self._input_stale = False
        if math.isfinite(value):
            self._input_error = ""
        else:
            self._invalid_input_count += 1
            self._input_error = "non-finite press_index ignored; valid release required"
            self._warn_limited(self._input_error)
            self._pending_target = None
        command = self._toggle.update(value)
        if command is not None:
            self._target = command
            self._pending_target = list(command)

    def _mark_input_lost(self):
        if not self._input_stale:
            self._toggle.input_lost()
            self._pending_target = None
            self._input_stale = True

    def _input_fresh(self):
        fresh = (self._last_input_s is not None and
                 time.monotonic() - self._last_input_s <= self._input_timeout_s)
        if not fresh and self._last_input_s is not None:
            self._mark_input_lost()
        return fresh

    def _communication_failed(self, operation, exc):
        self._communication_ok = False
        self._communication_error = f"{operation}: {exc}"
        self._warn_limited(self._communication_error)

    def _send_target(self):
        if self._connect_only:
            return
        if not self._input_fresh() or self._pending_target is None:
            return
        if self._dry_run:
            self._pending_target = None
            return
        if not self._communication_ok or self._fault_codes is None or any(self._fault_codes):
            self._pending_target = None
            return
        pose = self._pending_target
        self._pending_target = None
        try:
            self._hand.finger_move(pose=list(pose))
            self._communication_ok = True
            self._communication_error = ""
        except Exception as exc:
            self._communication_failed("finger_move", exc)

    def _poll_feedback(self):
        try:
            actual = seven_readings(self._hand.get_state(), "get_state")
            faults = seven_readings(self._hand.get_fault(), "get_fault")
            self._actual = actual
            self._fault_codes = faults
            self._communication_ok = True
            self._communication_error = ""
        except Exception as exc:
            self._actual = None
            self._fault_codes = None
            self._communication_failed("feedback", exc)

    def _publish_status(self):
        fresh = self._input_fresh()
        if self._connect_only:
            if not self._communication_ok:
                state = "COMM_ERROR"
            elif self._fault_codes is not None and any(self._fault_codes):
                state = "HAND_FAULT"
            else:
                state = "CONNECT_ONLY"
        elif not fresh:
            state = "INPUT_STALE"
        elif self._dry_run:
            state = "DRY_RUN"
        elif not self._communication_ok:
            state = "COMM_ERROR"
        elif self._fault_codes is not None and any(self._fault_codes):
            state = "HAND_FAULT"
        else:
            state = "READY"
        nanoseconds = self.get_clock().now().nanoseconds
        payload = {
            "stamp": {"sec": nanoseconds // 1_000_000_000,
                      "nanosec": nanoseconds % 1_000_000_000},
            "target": self._target,
            "trigger_value": self._toggle.trigger_value,
            "trigger_pressed": self._toggle.trigger_pressed,
            "trigger_armed": self._toggle.trigger_armed,
            "hand_toggle_state": self._toggle.hand_toggle_state,
            "actual": self._actual,
            "fault_codes": self._fault_codes,
            "communication_ok": self._communication_ok,
            "input_fresh": fresh,
            "dry_run": bool(self._dry_run),
            "connect_only": self._connect_only,
            "state": state,
            "error": self._communication_error or self._input_error,
            "invalid_input_count": self._invalid_input_count,
        }
        message = String()
        message.data = json.dumps(payload, separators=(",", ":"))
        self._status_pub.publish(message)

    def destroy_node(self):
        if self._hand is not None:
            transport = getattr(self._hand, "hand", self._hand)
            close = getattr(transport, "close", None)
            if close is not None:
                try:
                    close()
                except Exception as exc:
                    self._warn_limited(f"SDK close: {exc}")
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = RightLinkerHandNode()
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
