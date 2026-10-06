"""Display contract tests; no ROS or Qt installation is required."""
import json
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from rm65_teleop_dashboard.models import parse_adapter_status, parse_linkerhand_status


class AdapterParsingTests(unittest.TestCase):
    def test_current_status_values_are_preserved(self):
        result = parse_adapter_status(json.dumps({
            "state": "ACTIVE", "dry_run": False,
            "deadman_pressed": True, "command_path_ready": True,
            "home_action_state": "SUCCEEDED", "watchdog_count": 2,
            "joint_preset_selection": "X_FIRST",
        }))
        self.assertEqual(result.state, "ACTIVE")
        self.assertFalse(result.dry_run)
        self.assertTrue(result.deadman_pressed)
        self.assertEqual(result.watchdog_count, 2)
        self.assertEqual(result.home_action_state, "SUCCEEDED")
        self.assertEqual(result.joint_preset_selection, "X_FIRST")

    def test_missing_fields_and_invalid_json_are_visible_without_throwing(self):
        old = parse_adapter_status('{"state":"ARMED"}')
        self.assertIsNone(old.command_path_ready)
        self.assertIsNone(old.deadman_pressed)
        self.assertEqual(old.parse_error, "")
        for payload in ("broken{", "[]", "null", None):
            with self.subTest(payload=payload):
                result = parse_adapter_status(payload)
                self.assertEqual(result.state, "DATA_ERROR")
                self.assertTrue(result.parse_error)

    def test_nonfinite_and_wrong_types_never_reach_the_display(self):
        result = parse_adapter_status('{"state":"ACTIVE","robot_age_ms":NaN,'
                                      '"max_cycle_period_ms":Infinity,'
                                      '"watchdog_count":true,"deadman_pressed":1,'
                                      '"home_hold_progress":"0.5"}')
        self.assertIsNone(result.robot_age_ms)
        self.assertIsNone(result.max_cycle_period_ms)
        self.assertIsNone(result.watchdog_count)
        self.assertIsNone(result.deadman_pressed)
        self.assertIsNone(result.home_hold_progress)
        self.assertIn("robot_age_ms", result.parse_error)

    def test_oversized_numbers_and_recursive_malformed_json_do_not_throw(self):
        huge = parse_adapter_status(json.dumps({"robot_age_ms": 10 ** 400,
                                                "watchdog_count": 10 ** 400}))
        self.assertIsNone(huge.robot_age_ms)
        self.assertIsNone(huge.watchdog_count)
        recursive = parse_adapter_status("[" * 10000 + "]" * 10000)
        self.assertEqual(recursive.state, "DATA_ERROR")
        self.assertTrue(recursive.parse_error)


class HandParsingTests(unittest.TestCase):
    def test_real_seven_channel_feedback_and_startup_null(self):
        payload = {"state": "READY", "trigger_value": .4, "trigger_armed": True,
                   "hand_toggle_state": "OPEN", "target": [73, 0, 255, 255, 255, 255, 156],
                   "actual": [70, 0, 250, 250, 250, 250, 150], "fault_codes": [0] * 7,
                   "communication_ok": True, "input_fresh": True, "connect_only": False}
        result = parse_linkerhand_status(json.dumps(payload))
        self.assertEqual(result.target, tuple(payload["target"]))
        self.assertEqual(result.actual, tuple(payload["actual"]))
        self.assertEqual(result.fault_codes, (0,) * 7)
        self.assertEqual(result.hand_toggle_state, "OPEN")
        self.assertEqual(result.parse_error, "")
        startup = parse_linkerhand_status('{"state":"DRY_RUN","target":null,"actual":null}')
        self.assertIsNone(startup.target)
        self.assertIsNone(startup.actual)

    def test_hand_bad_arrays_are_unknown_and_reported(self):
        for bad in ([0] * 6, [0] * 8, [0] * 6 + [math.nan], "bad"):
            result = parse_linkerhand_status(json.dumps({"actual": bad}))
            self.assertIsNone(result.actual)
            self.assertIn("actual", result.parse_error)


if __name__ == "__main__":
    unittest.main()
