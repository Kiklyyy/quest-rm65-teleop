"""Demo snapshots are explicitly simulated, dynamic and finite."""
from dataclasses import fields, is_dataclass
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from rm65_teleop_dashboard.demo_data import demo_snapshot


class DemoTests(unittest.TestCase):
    def test_demo_is_dynamic_finite_six_joint_and_right_hand_only(self):
        first, second = demo_snapshot(0, "143"), demo_snapshot(2, "143")
        self.assertTrue(first.demo)
        self.assertEqual(first.domain_id, "143")
        self.assertEqual(first.left.adapter.state, "ACTIVE")
        self.assertEqual(first.right.adapter.state, "ARMED")
        self.assertEqual(len(first.left.joints_deg), 6)
        self.assertEqual(len(first.right.joints_deg), 6)
        self.assertEqual(len(first.linkerhand.actual), 7)
        self.assertNotEqual(first.left.robot_pose.position, second.left.robot_pose.position)
        self.assertEqual(first.left_controller.pose_health.hz, 72)
        self.assertEqual(first.right.robot_health.hz, 198)
        self.assertEqual(first.left.adapter.watchdog_count, 0)
        self.assertFalse(hasattr(first, "left_linkerhand"))
        self._check_finite(first)
        self._check_finite(second)

    def _check_finite(self, value):
        if is_dataclass(value):
            for field in fields(value):
                self._check_finite(getattr(value, field.name))
        elif isinstance(value, (tuple, list)):
            for item in value:
                self._check_finite(item)
        elif isinstance(value, float):
            self.assertTrue(math.isfinite(value))

    def test_simulated_ready_telemetry_uses_coherent_hardware_status_fields(self):
        snapshot = demo_snapshot()
        self.assertTrue(snapshot.demo)
        for arm in (snapshot.left, snapshot.right):
            self.assertFalse(arm.adapter.dry_run)
            self.assertTrue(arm.adapter.hardware_write_enabled)
            self.assertTrue(arm.adapter.hardware_output_available)
            self.assertTrue(arm.adapter.home_command_path_ready)
        self.assertFalse(snapshot.linkerhand.dry_run)
        self.assertEqual(snapshot.linkerhand.state, "READY")
        self.assertTrue(snapshot.linkerhand.communication_ok)


if __name__ == "__main__":
    unittest.main()
