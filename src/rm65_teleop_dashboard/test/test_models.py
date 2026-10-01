"""Pure model behavior and receive-time display tests."""
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from rm65_teleop_dashboard import models


class ModelTests(unittest.TestCase):
    def test_joint_state_is_reordered_and_bad_joint_is_unknown(self):
        names = ["joint3", "joint1", "joint6", "joint2", "joint5", "joint4"]
        result, error = models.reorder_joints(names, [3, 1, 6, 2, 5, 4])
        self.assertEqual(result, tuple(math.degrees(n) for n in range(1, 7)))
        self.assertEqual(error, "")
        result, error = models.reorder_joints(["joint1", "joint1", "joint3"], [1, 2, math.nan])
        self.assertEqual(result, (None,) * 6)
        self.assertIn("duplicate joint1", error)
        self.assertIn("missing joint2", error)
        self.assertIn("invalid joint3", error)

    def test_quaternion_normalization_pitch_singularity_and_invalid_values(self):
        self.assertEqual(models.quaternion_to_rpy(0, 0, 0, 2), (0, 0, 0))
        angles = models.quaternion_to_rpy(0, math.sqrt(0.5), 0, math.sqrt(0.5))
        self.assertAlmostEqual(angles[1], 90)
        self.assertTrue(all(math.isfinite(value) for value in angles))
        yaw = models.quaternion_to_rpy(0, 0, math.sqrt(0.5), math.sqrt(0.5))
        self.assertAlmostEqual(yaw[2], 90)
        for quaternion in ((0, 0, 0, 0), (math.inf, 0, 0, 1), (0, math.nan, 0, 1)):
            self.assertIsNone(models.quaternion_to_rpy(*quaternion))

    def test_receive_age_frequency_and_stale_are_monotonic_bounded(self):
        meter = models.FrequencyMeter(window_s=2, max_samples=100)
        self.assertEqual(meter.health(0).state, "OFFLINE")
        for index in range(101):
            meter.mark(index / 50)
        health = meter.health(2.01, stale_s=.2, lost_s=2)
        self.assertAlmostEqual(health.hz, 50)
        self.assertAlmostEqual(health.age_ms, 10)
        self.assertEqual(health.state, "ONLINE")
        self.assertEqual(meter.health(2.3, stale_s=.2, lost_s=2).state, "STALE")
        self.assertEqual(meter.health(5, stale_s=.2, lost_s=2).state, "OFFLINE")
        self.assertEqual(meter.health(5).hz, 0)
        meter.mark(1)  # Out-of-order receive timestamps do not rewind the meter.
        self.assertAlmostEqual(meter.health(5).age_ms, 3000)

    def test_numeric_conversion_overflow_cannot_create_infinite_display(self):
        self.assertFalse(models.finite_number(10 ** 400))
        joints, error = models.reorder_joints(models.JOINT_NAMES, [1e308] * 6)
        self.assertEqual(joints, (None,) * 6)
        self.assertTrue(error)
        self.assertIsNone(models.quaternion_to_rpy(1e308, 1e308, 1e308, 1e308))

    def test_store_immutable_snapshot_and_stale_adapter_does_not_claim_hardware(self):
        store = models.SnapshotStore(domain_id="143")
        initial = store.snapshot(10)
        self.assertEqual(initial.domain_id, "143")
        self.assertEqual(models.summarize_system(initial), "OFFLINE")
        store.update_pose("left", "robot", (1, 2, 3), (0, 0, 0, 1), 10)
        store.update_adapter("left", '{"state":"ARMED","dry_run":false}', 10)
        received = store.snapshot(10.01)
        self.assertEqual(received.left.robot_pose.position, (1, 2, 3))
        self.assertEqual(received.left.adapter.state, "ARMED")
        self.assertEqual(initial.left.robot_pose.position, None)
        expired = store.snapshot(12.5)
        self.assertEqual(expired.left.adapter.state, "OFFLINE")
        self.assertIsNone(expired.left.adapter.dry_run)
        self.assertEqual(models.operating_mode(expired), "UNKNOWN")
        store.set_monitor_error("executor unavailable")
        self.assertEqual(models.summarize_system(store.snapshot(12.5)), "FAULT")

    def test_inputs_joints_and_hand_are_received_without_nan_or_fake_values(self):
        store = models.SnapshotStore()
        store.update_inputs("right", math.nan, .8, True, False, 10)
        store.update_joints("right", models.JOINT_NAMES, [0, .1, .2, .3, .4, .5], 10)
        store.update_linkerhand('{"state":"READY","target":[73,0,255,255,255,255,156]}', 10)
        received = store.snapshot(10.01)
        self.assertIsNone(received.right_controller.grip)
        self.assertEqual(received.right_controller.trigger, .8)
        self.assertEqual(received.right_controller.inputs_health.state, "INVALID")
        self.assertAlmostEqual(received.right.joints_deg[5], math.degrees(.5))
        self.assertEqual(received.linkerhand.health.state, "ONLINE")
        self.assertIsNone(received.linkerhand.actual)
        self.assertEqual(store.snapshot(13).linkerhand.state, "OFFLINE")

    def test_status_presentations_cover_health_safety_and_unknown(self):
        self.assertEqual(models.status_color("ACTIVE"), "#36d5a4")
        self.assertEqual(models.status_color("ARMED"), "#4ea6ee")
        self.assertEqual(models.status_color("FAULT"), "#f27983")
        self.assertEqual(models.status_color("REARM_REQUIRED"), "#e8b367")
        self.assertEqual(models.status_color("UNRECOGNIZED_NEW_STATE"), "#8191a3")
        self.assertEqual(models.status_text("STALE"), "STALE")
        self.assertEqual(models.status_text(None), "UNKNOWN")
        self.assertEqual(models.status_tone("DATA_ERROR"), "red")
        self.assertEqual(models.status_tone("PRESSED"), "green")
        self.assertEqual(models.status_tone("CANCELING"), "orange")

    def test_event_logger_only_records_semantic_changes_and_bounds_history(self):
        from dataclasses import replace
        logger = models.EventLogger(max_records=5)
        base = models.SystemSnapshot(left=models.ArmSnapshot(side="left",
            adapter=models.AdapterStatus(state="ARMED")), time_s=100)
        first = logger.update(base)
        self.assertTrue(any(event.message == "ARMED" for event in first))
        self.assertEqual(logger.update(replace(base, time_s=101)), first)
        analog_only = replace(base, left_controller=models.ControllerSnapshot(grip=.9), time_s=102)
        self.assertEqual(logger.update(analog_only), first)
        fault = replace(base, left=replace(base.left,
            adapter=models.AdapterStatus(state="FAULT", reason="invalid_feedback")), time_s=103)
        changed = logger.update(fault)
        self.assertTrue(any(event.level == "ERROR" and "invalid_feedback" in event.message for event in changed))
        for index in range(20):
            logger.update(replace(base, left=replace(base.left,
                adapter=models.AdapterStatus(state="ARMED" if index % 2 else "ACTIVE"))))
        self.assertLessEqual(len(logger.update(base)), 5)

    def test_summary_degrades_unknown_adapter_and_stale_optional_hand(self):
        from dataclasses import replace
        from rm65_teleop_dashboard.demo_data import demo_snapshot
        normal = demo_snapshot()
        self.assertEqual(models.summarize_system(normal), "SYSTEM READY")
        unknown = replace(normal, left=replace(normal.left,
            adapter=replace(normal.left.adapter, state="NEW_UNKNOWN_STATE")))
        self.assertEqual(models.summarize_system(unknown), "DEGRADED")
        stale_hand = replace(normal, linkerhand=replace(normal.linkerhand,
            health=models.StreamHealth("STALE", 600, 0)))
        self.assertEqual(models.summarize_system(stale_hand), "DEGRADED")
        absent_hand = replace(normal, linkerhand=models.LinkerHandSnapshot())
        self.assertEqual(models.summarize_system(absent_hand), "SYSTEM READY")
        lost_hand = replace(normal, linkerhand=models.LinkerHandSnapshot(
            health=models.StreamHealth("OFFLINE", 2500, 0)))
        self.assertEqual(models.summarize_system(lost_hand), "DEGRADED")
        target_lost = replace(normal, left=replace(normal.left, target_health=models.StreamHealth()))
        self.assertEqual(models.summarize_system(target_lost), "DEGRADED")


if __name__ == "__main__":
    unittest.main()
