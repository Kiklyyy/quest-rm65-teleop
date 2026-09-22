#!/usr/bin/env python3
"""Bounded synthetic 6DoF dry-run probe for rm65_teleop_adapter."""

import json
import math
import time
from collections.abc import Callable, Sequence

import rclpy
from geometry_msgs.msg import Pose, PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.node import Node
from std_msgs.msg import String


HARDWARE_COMMAND_TOPIC = "/right/rm_driver/movep_canfd_cmd"


def quaternion_from_axis_angle(
        axis_xyz: Sequence[float], angle_rad: float) -> list[float]:
    norm = math.sqrt(sum(value * value for value in axis_xyz))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("axis must be finite and nonzero")
    sine = math.sin(angle_rad / 2.0)
    quaternion = [
        axis_xyz[0] * sine / norm,
        axis_xyz[1] * sine / norm,
        axis_xyz[2] * sine / norm,
        math.cos(angle_rad / 2.0),
    ]
    result_norm = quaternion_norm(quaternion)
    return [value / result_norm for value in quaternion]


def quaternion_norm(quaternion_xyzw: Sequence[float]) -> float:
    x, y, z, w = quaternion_xyzw
    return math.sqrt(x * x + y * y + z * z + w * w)


def shortest_angle(
        lhs_xyzw: Sequence[float], rhs_xyzw: Sequence[float]) -> float:
    lhs_norm = quaternion_norm(lhs_xyzw)
    rhs_norm = quaternion_norm(rhs_xyzw)
    if lhs_norm <= 0.0 or rhs_norm <= 0.0:
        raise AssertionError("shortest_angle received zero quaternion")
    dot = sum(
        lhs_xyzw[index] * rhs_xyzw[index]
        for index in range(4)) / (lhs_norm * rhs_norm)
    return 2.0 * math.acos(max(0.0, min(1.0, abs(dot))))


def assert_quaternion_close(
        actual_xyzw: Sequence[float],
        expected_xyzw: Sequence[float],
        tolerance_rad: float) -> None:
    error = shortest_angle(actual_xyzw, expected_xyzw)
    if error > tolerance_rad:
        raise AssertionError(
            f"quaternion mismatch: actual={list(actual_xyzw)}, "
            f"expected={list(expected_xyzw)}, angular_error={error}")


def quaternion_multiply(
        lhs_xyzw: Sequence[float], rhs_xyzw: Sequence[float]) -> list[float]:
    lx, ly, lz, lw = lhs_xyzw
    rx, ry, rz, rw = rhs_xyzw
    result = [
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    ]
    norm = quaternion_norm(result)
    return [value / norm for value in result]


def quaternion_from_pose(pose: Pose) -> list[float]:
    return [
        pose.orientation.x,
        pose.orientation.y,
        pose.orientation.z,
        pose.orientation.w,
    ]


def position_from_pose(pose: Pose) -> list[float]:
    return [pose.position.x, pose.position.y, pose.position.z]


def position_error(lhs: Sequence[float], rhs: Sequence[float]) -> float:
    return math.sqrt(sum((lhs[i] - rhs[i]) ** 2 for i in range(3)))


class DryRun6DofProbe(Node):

    def __init__(self) -> None:
        super().__init__("dry_run_6dof_probe")
        self.target_position = [0.0, 0.0, 0.0]
        self.quest_orientation = [0.0, 0.0, 0.0, 1.0]
        self.robot_position = [0.4, 0.0, 0.5]
        self.robot_orientation = [0.0, 0.0, 0.0, 1.0]
        self.press_middle = 0.0

        self.previews: list[PoseStamped] = []
        self.statuses: list[dict] = []
        self.callback_errors: list[str] = []
        self.continuity_enabled = False
        self.continuity_previous: list[float] | None = None

        self.target_publisher = self.create_publisher(
            PoseStamped, "/quest_right_target_pose", 10)
        self.quest_publisher = self.create_publisher(
            PoseStamped, "/q2r_right_hand_pose", 10)
        self.input_publisher = self.create_publisher(
            OVR2ROSInputs, "/q2r_right_hand_inputs", 10)
        self.robot_publisher = self.create_publisher(
            Pose, "/right/rm_driver/udp_arm_position", 10)
        self.preview_subscription = self.create_subscription(
            PoseStamped,
            "/right/rm65_teleop/preview_target_pose",
            self._preview_callback,
            10)
        self.status_subscription = self.create_subscription(
            String, "/right/rm65_teleop/status", self._status_callback, 10)
        self.publish_timer = self.create_timer(0.01, self._publish_inputs)

    def _publish_inputs(self) -> None:
        stamp = self.get_clock().now().to_msg()

        target = PoseStamped()
        target.header.stamp = stamp
        target.pose.position.x, target.pose.position.y, target.pose.position.z = (
            self.target_position)
        target.pose.orientation.w = 1.0
        self.target_publisher.publish(target)

        quest = PoseStamped()
        quest.header.stamp = stamp
        quest.pose.position.x = 0.1
        quest.pose.position.y = 0.2
        quest.pose.position.z = 0.3
        (
            quest.pose.orientation.x,
            quest.pose.orientation.y,
            quest.pose.orientation.z,
            quest.pose.orientation.w,
        ) = self.quest_orientation
        self.quest_publisher.publish(quest)

        inputs = OVR2ROSInputs()
        inputs.press_middle = float(self.press_middle)
        self.input_publisher.publish(inputs)

        robot = Pose()
        robot.position.x, robot.position.y, robot.position.z = self.robot_position
        (
            robot.orientation.x,
            robot.orientation.y,
            robot.orientation.z,
            robot.orientation.w,
        ) = self.robot_orientation
        self.robot_publisher.publish(robot)

    def _preview_callback(self, message: PoseStamped) -> None:
        quaternion = quaternion_from_pose(message.pose)
        if not all(math.isfinite(value) for value in quaternion):
            self.callback_errors.append(f"nonfinite preview quaternion: {quaternion}")
        norm = quaternion_norm(quaternion)
        if abs(norm - 1.0) > 1.0e-9:
            self.callback_errors.append(
                f"preview quaternion norm {norm} outside 1e-9: {quaternion}")
        if self.continuity_enabled and self.continuity_previous is not None:
            distance = shortest_angle(self.continuity_previous, quaternion)
            if distance > 0.05:
                self.callback_errors.append(
                    f"preview orientation discontinuity {distance} rad")
        if self.continuity_enabled:
            self.continuity_previous = quaternion
        self.previews.append(message)

    def _status_callback(self, message: String) -> None:
        try:
            status = json.loads(message.data)
            if "state" not in status or "reason" not in status:
                raise AssertionError(f"status missing state/reason: {status}")
            self.statuses.append(status)
        except (json.JSONDecodeError, AssertionError) as error:
            self.callback_errors.append(str(error))

    def wait_for(
            self,
            predicate: Callable[[], bool],
            timeout_sec: float,
            description: str) -> None:
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.02)
            if self.callback_errors:
                raise AssertionError(self.callback_errors[0])
            if predicate():
                return
        raise AssertionError(f"timeout waiting for {description}")

    def spin_for(self, duration_sec: float) -> None:
        deadline = time.monotonic() + duration_sec
        self.wait_for(
            lambda: time.monotonic() >= deadline,
            duration_sec + 0.5,
            f"{duration_sec:.3f}s spin interval")

    def latest_state(self) -> str:
        return self.statuses[-1]["state"] if self.statuses else ""


def main() -> None:
    rclpy.init()
    probe = DryRun6DofProbe()
    phases: list[str] = []
    try:
        probe.wait_for(
            lambda: (
                probe.target_publisher.get_subscription_count() > 0 and
                probe.quest_publisher.get_subscription_count() > 0 and
                probe.input_publisher.get_subscription_count() > 0 and
                probe.robot_publisher.get_subscription_count() > 0 and
                bool(probe.statuses)),
            5.0,
            "adapter subscriptions and first status")

        if probe.count_publishers(HARDWARE_COMMAND_TOPIC) != 0:
            raise AssertionError("dry-run created a hardware command publisher")

        # released_baseline
        probe.press_middle = 0.0
        probe.wait_for(
            lambda: probe.latest_state() == "ARMED",
            5.0,
            "released_baseline ARMED state")
        phases.append("released_baseline")

        # press_anchor
        preview_start = len(probe.previews)
        probe.press_middle = 1.0
        probe.wait_for(
            lambda: len(probe.previews) > preview_start,
            5.0,
            "first press preview")
        first_preview = probe.previews[preview_start].pose
        if position_error(
                position_from_pose(first_preview), probe.robot_position) > 1.0e-9:
            raise AssertionError("first press position jumped from robot anchor")
        assert_quaternion_close(
            quaternion_from_pose(first_preview), probe.robot_orientation, 1.0e-9)
        phases.append("press_anchor")

        # quest_x_rotation
        probe.continuity_enabled = True
        probe.continuity_previous = quaternion_from_pose(probe.previews[-1].pose)
        for index in range(1, 9):
            probe.quest_orientation = quaternion_from_axis_angle(
                [1.0, 0.0, 0.0], 0.005 * index)
            probe.spin_for(0.03)
        expected_x_mapping = quaternion_from_axis_angle(
            [0.0, -1.0, 0.0], 0.04)
        probe.wait_for(
            lambda: (
                bool(probe.previews) and
                shortest_angle(
                    quaternion_from_pose(probe.previews[-1].pose),
                    expected_x_mapping) < 2.0e-3),
            5.0,
            "Quest +X to RM -Y orientation convergence")
        phases.append("quest_x_rotation")

        # combined_motion
        combined_start_pose = probe.previews[-1].pose
        combined_start_position = position_from_pose(combined_start_pose)
        combined_start_orientation = quaternion_from_pose(combined_start_pose)
        qx = quaternion_from_axis_angle([1.0, 0.0, 0.0], 0.04)
        for index in range(1, 11):
            fraction = index / 10.0
            probe.target_position[0] = 0.002 * fraction
            qy = quaternion_from_axis_angle(
                [0.0, 1.0, 0.0], 0.03 * fraction)
            probe.quest_orientation = quaternion_multiply(qy, qx)
            probe.spin_for(0.03)
        probe.wait_for(
            lambda: (
                position_error(
                    position_from_pose(probe.previews[-1].pose),
                    combined_start_position) > 1.0e-4 and
                shortest_angle(
                    quaternion_from_pose(probe.previews[-1].pose),
                    combined_start_orientation) > 0.01),
            5.0,
            "simultaneous translation and non-commuting rotation")
        phases.append("combined_motion")

        # release_freeze
        probe.press_middle = 0.0
        probe.continuity_enabled = False
        probe.wait_for(
            lambda: probe.latest_state() in ("REARM_REQUIRED", "ARMED"),
            5.0,
            "release stop/rearm")
        probe.spin_for(0.05)
        released_preview_count = len(probe.previews)
        probe.target_position = [0.1, -0.1, 0.05]
        probe.quest_orientation = quaternion_from_axis_angle(
            [0.0, 0.0, 1.0], 1.0)
        probe.spin_for(0.25)
        if len(probe.previews) != released_preview_count:
            raise AssertionError("preview continued after deadman release")
        phases.append("release_freeze")

        # repress_anchor
        probe.robot_position = [0.42, 0.02, 0.52]
        probe.robot_orientation = quaternion_from_axis_angle(
            [0.0, 0.0, 1.0], 0.2)
        probe.wait_for(
            lambda: probe.latest_state() == "ARMED",
            5.0,
            "ARMED before repress")
        probe.spin_for(0.10)
        repress_start = len(probe.previews)
        probe.press_middle = 1.0
        probe.wait_for(
            lambda: len(probe.previews) > repress_start,
            5.0,
            "first repress preview")
        repress_preview = probe.previews[repress_start].pose
        if position_error(
                position_from_pose(repress_preview), probe.robot_position) > 1.0e-9:
            raise AssertionError("repress position did not use new robot anchor")
        assert_quaternion_close(
            quaternion_from_pose(repress_preview),
            probe.robot_orientation,
            1.0e-9)
        phases.append("repress_anchor")

        # final_checks
        if not probe.statuses:
            raise AssertionError("no status messages observed")
        if probe.callback_errors:
            raise AssertionError(probe.callback_errors[0])
        hardware_publishers = probe.count_publishers(HARDWARE_COMMAND_TOPIC)
        if hardware_publishers != 0:
            raise AssertionError(
                f"hardware command publisher count is {hardware_publishers}, expected 0")
        phases.append("final_checks")
        print(json.dumps({
            "result": "synthetic dry-run verified",
            "phases": phases,
            "preview_count": len(probe.previews),
            "status_count": len(probe.statuses),
            "hardware_command_publisher_count": hardware_publishers,
        }, sort_keys=True))
    finally:
        probe.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
