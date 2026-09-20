import time

import rclpy
from geometry_msgs.msg import PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.node import Node
from visualization_msgs.msg import Marker

from .quest_right_target_logic import QuestRightTargetLogic

POSE_TOPIC = "/q2r_right_hand_pose"
INPUTS_TOPIC = "/q2r_right_hand_inputs"
TARGET_POSE_TOPIC = "/quest_right_target_pose"
TARGET_MARKER_TOPIC = "/quest_right_target_marker"
WORLD_FRAME = "world"
TIMER_PERIOD_S = 0.02
MARKER_NAMESPACE = "quest_right_target"
MARKER_ID = 0
MARKER_SCALE_M = 0.06
MARKER_COLOR_RGBA = (0.1, 1.0, 0.2, 0.9)


def build_target_pose(target: tuple[float, float, float], stamp) -> PoseStamped:
    message = PoseStamped()
    message.header.frame_id = WORLD_FRAME
    message.header.stamp = stamp
    message.pose.position.x, message.pose.position.y, message.pose.position.z = target
    message.pose.orientation.x = 0.0
    message.pose.orientation.y = 0.0
    message.pose.orientation.z = 0.0
    message.pose.orientation.w = 1.0
    return message


def build_target_marker(target: tuple[float, float, float], stamp) -> Marker:
    marker = Marker()
    marker.header.frame_id = WORLD_FRAME
    marker.header.stamp = stamp
    marker.ns = MARKER_NAMESPACE
    marker.id = MARKER_ID
    marker.type = Marker.SPHERE
    marker.action = Marker.ADD
    marker.pose.position.x, marker.pose.position.y, marker.pose.position.z = target
    marker.pose.orientation.x = 0.0
    marker.pose.orientation.y = 0.0
    marker.pose.orientation.z = 0.0
    marker.pose.orientation.w = 1.0
    marker.scale.x = MARKER_SCALE_M
    marker.scale.y = MARKER_SCALE_M
    marker.scale.z = MARKER_SCALE_M
    marker.color.r, marker.color.g, marker.color.b, marker.color.a = MARKER_COLOR_RGBA
    return marker


class QuestRightTargetBridge(Node):
    def __init__(self) -> None:
        super().__init__("quest_right_target_bridge")
        self._logic = QuestRightTargetLogic()
        self._pose_subscription = self.create_subscription(
            PoseStamped, POSE_TOPIC, self._pose_callback, 10)
        self._inputs_subscription = self.create_subscription(
            OVR2ROSInputs, INPUTS_TOPIC, self._inputs_callback, 10)
        self._target_pose_publisher = self.create_publisher(
            PoseStamped, TARGET_POSE_TOPIC, 10)
        self._target_marker_publisher = self.create_publisher(
            Marker, TARGET_MARKER_TOPIC, 10)
        self._timer = self.create_timer(TIMER_PERIOD_S, self._timer_callback)

    def _pose_callback(self, msg: PoseStamped) -> None:
        position = (
            msg.pose.position.x,
            msg.pose.position.y,
            msg.pose.position.z,
        )
        self._logic.update_pose(position, time.monotonic())

    def _inputs_callback(self, msg: OVR2ROSInputs) -> None:
        self._logic.update_deadman(bool(msg.button_lower), time.monotonic())

    def _timer_callback(self) -> None:
        self._logic.check_timeout(time.monotonic())
        stamp = self.get_clock().now().to_msg()
        target = self._logic.target
        self._target_pose_publisher.publish(build_target_pose(target, stamp))
        self._target_marker_publisher.publish(build_target_marker(target, stamp))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = QuestRightTargetBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
