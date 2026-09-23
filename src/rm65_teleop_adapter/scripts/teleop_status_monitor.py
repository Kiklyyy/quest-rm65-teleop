#!/usr/bin/env python3

import time

import rclpy
from geometry_msgs.msg import Pose, PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from teleop_status_logic import TeleopStatusModel


class TeleopStatusMonitor(Node):
    """Read-only summary of right-arm teleoperation topic health."""

    def __init__(self) -> None:
        super().__init__("teleop_status_monitor")
        stream_timeout_s = self.declare_parameter("stream_timeout_s", 0.5).value
        adapter_timeout_s = self.declare_parameter("adapter_timeout_s", 0.5).value
        heartbeat_s = self.declare_parameter("heartbeat_s", 1.0).value
        check_period_s = self.declare_parameter("check_period_s", 0.1).value
        self._model = TeleopStatusModel(
            stream_timeout_s=stream_timeout_s,
            adapter_timeout_s=adapter_timeout_s,
            heartbeat_s=heartbeat_s,
        )

        self._quest_subscription = self.create_subscription(
            PoseStamped,
            "/q2r_right_hand_pose",
            lambda _: self._mark("quest"),
            10,
        )
        self._inputs_subscription = self.create_subscription(
            OVR2ROSInputs,
            "/q2r_right_hand_inputs",
            lambda _: self._mark("inputs"),
            10,
        )
        self._target_subscription = self.create_subscription(
            PoseStamped,
            "/quest_right_target_pose",
            lambda _: self._mark("target"),
            10,
        )
        self._robot_subscription = self.create_subscription(
            Pose,
            "/right/rm_driver/udp_arm_position",
            lambda _: self._mark("robot"),
            10,
        )
        self._joint_subscription = self.create_subscription(
            JointState,
            "/right/joint_states",
            lambda _: self._mark("joints"),
            10,
        )
        self._status_subscription = self.create_subscription(
            String,
            "/right/rm65_teleop/status",
            self._status_callback,
            10,
        )
        self._timer = self.create_timer(check_period_s, self._timer_callback)

    def _mark(self, stream: str) -> None:
        self._model.mark_stream(stream, time.monotonic())

    def _status_callback(self, message: String) -> None:
        self._model.update_adapter(message.data, time.monotonic())

    def _timer_callback(self) -> None:
        line = self._model.take_line_if_due(time.monotonic())
        if line is not None:
            self.get_logger().info(line)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TeleopStatusMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
