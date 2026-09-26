"""Isolated left Quest target + shared adapter preview; no hardware endpoint."""

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time

import rclpy
from geometry_msgs.msg import Pose, PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rm_ros_interfaces.msg import Cartepos
from std_msgs.msg import Empty, String


ROOT = Path(__file__).resolve().parents[3]
ADAPTER = ROOT / "build/rm65_teleop_adapter/rm65_teleop_adapter_node"
BRIDGE = ROOT / "install/q2r2_bringup/lib/q2r2_bringup/quest_target_bridge"
CONFIG = ROOT / "src/rm65_teleop_adapter/config/left_dry_run.yaml"


class Probe(Node):
    def __init__(self):
        super().__init__("left_dry_run_probe")
        self.quest_x = 0.0
        self.quest_angle = 0.0
        self.grip = 0.0
        self.statuses = []
        self.previews = []
        self.targets = []
        self.pose_pub = self.create_publisher(PoseStamped, "/q2r_left_hand_pose", 10)
        self.inputs_pub = self.create_publisher(OVR2ROSInputs, "/q2r_left_hand_inputs", 10)
        self.robot_pub = self.create_publisher(Pose, "/left/rm_driver/udp_arm_position", 10)
        self.create_subscription(String, "/left/rm65_teleop/status", self._status, 10)
        self.create_subscription(PoseStamped, "/left/rm65_teleop/preview_target_pose", self.previews.append, 10)
        self.create_subscription(PoseStamped, "/quest_left_target_pose", self.targets.append, 10)
        self.create_timer(0.02, self.publish_samples)

    def _status(self, message):
        self.statuses.append(json.loads(message.data))

    def publish_samples(self):
        quest = PoseStamped()
        quest.header.frame_id = "world"
        quest.pose.position.x = self.quest_x
        quest.pose.orientation.x = math.sin(self.quest_angle / 2.0)
        quest.pose.orientation.w = math.cos(self.quest_angle / 2.0)
        self.pose_pub.publish(quest)
        inputs = OVR2ROSInputs()
        inputs.press_middle = self.grip
        inputs.button_upper = True  # Must not activate left Home or motion.
        inputs.button_lower = True
        self.inputs_pub.publish(inputs)
        robot = Pose()
        robot.position.z = 0.5
        robot.orientation.w = 1.0
        self.robot_pub.publish(robot)


def wait_for(predicate, description, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(f"timeout waiting for {description}")


def test_left_dry_run_consumes_left_quest_and_never_opens_hardware_path():
    assert os.environ.get("ROS_DOMAIN_ID") == "143"
    assert os.environ.get("ROS_LOCALHOST_ONLY") == "1"
    rclpy.init()
    probe = Probe()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(probe)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    processes = []
    try:
        with tempfile.TemporaryDirectory(prefix="left_dry_run_") as temp:
            log_paths = [Path(temp) / "bridge.log", Path(temp) / "adapter.log"]
            logs = [path.open("w", encoding="utf-8") for path in log_paths]
            try:
                processes.append(subprocess.Popen([
                    str(BRIDGE), "--ros-args", "-r", "__node:=quest_left_target_bridge",
                    "-p", "pose_topic:=/q2r_left_hand_pose",
                    "-p", "inputs_topic:=/q2r_left_hand_inputs",
                    "-p", "target_topic:=/quest_left_target_pose",
                    "-p", "marker_topic:=/quest_left_target_marker",
                    "-p", "marker_namespace:=quest_left_target",
                ], stdout=logs[0], stderr=subprocess.STDOUT))
                processes.append(subprocess.Popen([
                    str(ADAPTER), "--ros-args", "-r", "__node:=left_rm65_teleop_adapter",
                    "--params-file", str(CONFIG),
                ], stdout=logs[1], stderr=subprocess.STDOUT))
                wait_for(lambda: len(probe.targets) > 0, "left target")
                wait_for(lambda: any(s.get("state") == "ARMED" and
                                     s.get("quest_pose_fresh") and s.get("inputs_fresh") and
                                     s.get("robot_fresh") for s in probe.statuses),
                         "fresh left inputs and ARMED")
                assert probe.previews == []  # Released Grip cannot preview a motion.
                probe.grip = 0.8
                wait_for(lambda: any(s.get("state") == "ACTIVE" for s in probe.statuses),
                         "left dry-run ACTIVE")
                probe.quest_x = 0.03
                probe.quest_angle = 0.05
                wait_for(lambda: any(p.pose.position.y < -0.0001 for p in probe.previews),
                         "Quest +X to left -Y preview")
                wait_for(lambda: any(p.pose.orientation.y < -0.001 for p in probe.previews),
                         "Quest +X rotation to left -Y orientation")
                assert probe.count_publishers("/left/rm_driver/movep_canfd_cmd") == 0
                assert probe.count_publishers("/left/rm_driver/move_stop_cmd") == 0
                assert probe.count_publishers("/left/rm_driver/movej_canfd_cmd") == 0
                clients = probe.get_client_names_and_types_by_node(
                    "left_rm65_teleop_adapter", "/")
                assert not any("/left/rm_group_controller/follow_joint_trajectory/_action/"
                               in name for name, _ in clients)
                assert all(s.get("home_action_state") == "DISABLED" for s in probe.statuses)
                assert all(s.get("hardware_output_available") is False for s in probe.statuses)
                probe.grip = 0.0
                wait_for(lambda: probe.statuses and probe.statuses[-1].get("state") != "ACTIVE",
                         "release leaves ACTIVE")
            except Exception:
                for path in log_paths:
                    print(path.name, path.read_text(encoding="utf-8"))
                raise
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        process.send_signal(signal.SIGINT)
                        process.wait(timeout=5)
                for log in logs:
                    log.close()
    finally:
        executor.shutdown(timeout_sec=5)
        thread.join(timeout=5)
        probe.destroy_node()
        rclpy.shutdown()
