"""Isolated right Home integration: all topics and action names are test-only."""

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time

import yaml
import rclpy
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import Pose, PoseStamped
from quest2ros.msg import OVR2ROSInputs
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rm_ros_interfaces.msg import Cartepos
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty, String

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "src" / "rm65_teleop_adapter"
EXECUTABLE = ROOT / "build" / "rm65_teleop_adapter" / "rm65_teleop_adapter_node"
PREFIX = "/test/home"


class SyntheticHome(Node):
    def __init__(self):
        super().__init__("synthetic_home_probe")
        self.button = False
        self.grip = 0.0
        self.publish_quest = True
        self.invalid_joints = False
        self.quest_x = 0.0
        self.statuses = []
        self.command_count = 0
        self.stop_count = 0
        self.goals = []
        self.cancel_count = 0
        self.goal_handle = None
        self.terminal_gate = threading.Event()
        self.abort_gate = threading.Event()
        self.poses = self.create_publisher(PoseStamped, PREFIX + "/quest_pose", 10)
        self.targets = self.create_publisher(PoseStamped, PREFIX + "/target", 10)
        self.inputs = self.create_publisher(OVR2ROSInputs, PREFIX + "/inputs", 10)
        self.robot = self.create_publisher(Pose, PREFIX + "/robot_pose", 10)
        self.joints = self.create_publisher(JointState, PREFIX + "/joints", 10)
        self.command_sub = self.create_subscription(
            Cartepos, PREFIX + "/movep_cmd", self._command, 10)
        self.stop_sub = self.create_subscription(
            Empty, PREFIX + "/stop", self._stop, 10)
        self.status_sub = self.create_subscription(
            String, "/right/rm65_teleop/status", self._status, 10)
        self.action = ActionServer(
            self, FollowJointTrajectory, PREFIX + "/action",
            execute_callback=self._execute,
            goal_callback=self._goal,
            cancel_callback=self._cancel,
            callback_group=ReentrantCallbackGroup(),
        )
        self.timer = self.create_timer(0.02, self._publish)

    def _command(self, _):
        self.command_count += 1

    def _stop(self, _):
        self.stop_count += 1

    def _status(self, message):
        try:
            self.statuses.append((time.monotonic(), json.loads(message.data)))
        except json.JSONDecodeError:
            pass

    def _goal(self, request):
        self.goals.append(request)
        self.terminal_gate.clear()
        return GoalResponse.ACCEPT

    def _cancel(self, _):
        self.cancel_count += 1
        return CancelResponse.ACCEPT

    def _execute(self, handle):
        self.goal_handle = handle
        while not self.terminal_gate.is_set() and not self.abort_gate.is_set():
            time.sleep(0.005)
        result = FollowJointTrajectory.Result()
        if handle.is_cancel_requested:
            handle.canceled()
        elif self.abort_gate.is_set():
            handle.abort()
        else:
            handle.succeed()
        return result

    def _publish(self):
        pose = PoseStamped()
        pose.pose.position.x = self.quest_x
        pose.pose.orientation.w = 1.0
        if self.publish_quest:
            self.poses.publish(pose)
        target = PoseStamped()
        target.pose.position.x = self.quest_x
        target.pose.orientation.w = 1.0
        self.targets.publish(target)
        inputs = OVR2ROSInputs()
        inputs.button_upper = self.button
        inputs.button_lower = True  # A has no Home authority.
        inputs.press_middle = self.grip
        self.inputs.publish(inputs)
        robot = Pose()
        robot.position.x = 0.4
        robot.position.z = 0.5
        robot.orientation.w = 1.0
        self.robot.publish(robot)
        joints = JointState()
        joints.name = ["joint3", "joint1", "joint6", "joint2", "joint5", "joint4"]
        joints.position = [0.3, 0.1, 0.6, 0.2, 0.5, 0.4]
        if self.invalid_joints:
            joints.name[-1] = "joint5"
        self.joints.publish(joints)

    def latest_state(self):
        return self.statuses[-1][1].get("state") if self.statuses else None


def wait_for(predicate, label, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(f"timeout waiting for {label}")


def saw_state(node, state, start):
    return any(item.get("state") == state for _, item in node.statuses[start:])


def test_home_synthetic_probe():
    assert os.environ.get("ROS_DOMAIN_ID") == "143"
    assert os.environ.get("ROS_LOCALHOST_ONLY") == "1"
    assert EXECUTABLE.exists()
    rclpy.init()
    node = SyntheticHome()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="synthetic_home_") as temp:
            override_path = Path(temp) / "override.yaml"
            log_path = Path(temp) / "adapter.log"
            override = {"rm65_teleop_adapter": {"ros__parameters": {
                "target_topic": PREFIX + "/target",
                "quest_pose_topic": PREFIX + "/quest_pose",
                "inputs_topic": PREFIX + "/inputs",
                "robot_pose_topic": PREFIX + "/robot_pose",
                "joint_state_topic": PREFIX + "/joints",
                "command_topic": PREFIX + "/movep_cmd",
                "stop_topic": PREFIX + "/stop",
                "home_action_name": PREFIX + "/action",
            }}}
            override_path.write_text(yaml.safe_dump(override), encoding="utf-8")
            command = [str(EXECUTABLE), "--ros-args", "--params-file",
                       str(PACKAGE / "config" / "hardware.yaml"),
                       "--params-file", str(override_path)]
            with log_path.open("w", encoding="utf-8") as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                try:
                    wait_for(lambda: node.latest_state() == "ARMED", "initial ARMED", 8)
                    initial_status = node.statuses[-1][1]
                    for field in ("quest_pose_age_ms", "inputs_age_ms", "robot_age_ms"):
                        assert isinstance(initial_status[field], (int, float))
                        assert initial_status[field] >= 0
                    assert isinstance(initial_status["joint_state_age_ms"], (int, float))
                    assert initial_status["joint_state_age_ms"] >= -1
                    wait_for(lambda: node.statuses[-1][1].get("joint_state_age_ms", -1) >= 0,
                             "first joint-state age")
                    assert initial_status["rearm_count"] == 0
                    assert initial_status["watchdog_count"] == 0
                    assert initial_status["home_action_state"] in ("IDLE", "SERVER_UNAVAILABLE")
                    assert node.count_publishers("/right/rm_driver/movep_canfd_cmd") == 0
                    assert not any("rm_driver" in name for name, _ in node.get_node_names_and_namespaces())

                    # A short B hold cannot create a goal.
                    node.button = True
                    time.sleep(0.7)
                    assert len(node.goals) == 0
                    wait_for(lambda: len(node.goals) == 1, "first Home goal", 3)
                    wait_for(lambda: node.latest_state() == "HOMING", "first HOMING")
                    first_goal = node.goals[0]
                    assert first_goal.trajectory.joint_names == [f"joint{i}" for i in range(1, 7)]
                    assert len(first_goal.trajectory.points) == 1
                    actual_positions = first_goal.trajectory.points[0].positions
                    expected_degrees = [-95.605, 4.406, -80.034, -22.695, -48.462, 97.570]
                    current_radians = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
                    assert all(math.isfinite(x) for x in actual_positions)
                    for actual, degrees in zip(actual_positions, expected_degrees):
                        assert math.isclose(actual, math.radians(degrees), abs_tol=1e-9)
                    duration_msg = first_goal.trajectory.points[0].time_from_start
                    duration = duration_msg.sec + duration_msg.nanosec * 1e-9
                    assert duration > 0
                    assert max(abs(a - c) for a, c in zip(actual_positions, current_radians)) <= \
                        duration * math.radians(15.0) + 1e-8
                    node.grip = 1.0
                    node.quest_x = 0.01
                    time.sleep(0.3)
                    assert node.command_count == 0
                    assert node.latest_state() == "HOMING"

                    # Cancel is requested immediately; the action result is deliberately held back.
                    state_start = len(node.statuses)
                    stop_before = node.stop_count
                    node.button = False
                    wait_for(lambda: node.cancel_count == 1, "first cancel request")
                    wait_for(lambda: node.stop_count > stop_before, "button-release stop")
                    time.sleep(0.3)
                    assert node.latest_state() == "HOMING"
                    assert not saw_state(node, "REARM_REQUIRED", state_start)
                    node.terminal_gate.set()
                    wait_for(lambda: saw_state(node, "REARM_REQUIRED", state_start),
                             "canceled terminal rearm")
                    assert node.command_count == 0

                    # Release Grip and B, then re-hold B for a successful Home.
                    node.grip = 0.0
                    wait_for(lambda: node.latest_state() == "ARMED", "rearm after cancel")
                    node.button = True
                    wait_for(lambda: len(node.goals) == 2, "second Home goal", 3)
                    node.grip = 1.0
                    state_start = len(node.statuses)
                    node.terminal_gate.set()
                    wait_for(lambda: saw_state(node, "REARM_REQUIRED", state_start),
                             "success terminal rearm")
                    time.sleep(1.7)
                    assert len(node.goals) == 2  # Continuous B cannot retrigger.
                    assert node.command_count == 0

                    # A fresh B release and hold starts Home again; Quest loss cancels it.
                    node.button = False
                    node.grip = 0.0
                    wait_for(lambda: node.latest_state() == "ARMED", "second rearm")
                    node.button = True
                    wait_for(lambda: len(node.goals) == 3, "third Home goal", 3)
                    node.grip = 1.0
                    stop_before = node.stop_count
                    node.publish_quest = False
                    wait_for(lambda: node.cancel_count == 2, "watchdog cancel", 3)
                    wait_for(lambda: node.stop_count > stop_before, "watchdog stop")
                    wait_for(lambda: node.statuses[-1][1].get("watchdog_count", 0) >= 1,
                             "watchdog diagnostic counter")
                    assert node.latest_state() == "HOMING"
                    state_start = len(node.statuses)
                    node.terminal_gate.set()
                    wait_for(lambda: saw_state(node, "REARM_REQUIRED", state_start),
                             "watchdog canceled rearm")
                    node.publish_quest = True
                    time.sleep(0.4)
                    assert node.latest_state() == "REARM_REQUIRED"
                    assert node.command_count == 0
                    assert node.count_publishers("/right/rm_driver/movep_canfd_cmd") == 0

                    # Invalid shuffled joint feedback is distinct from a stale stream.
                    node.button = False
                    node.grip = 0.0
                    wait_for(lambda: node.latest_state() == "ARMED", "third rearm")
                    node.button = True
                    wait_for(lambda: len(node.goals) == 4, "invalid-joint Home goal", 3)
                    node.grip = 1.0
                    node.invalid_joints = True
                    wait_for(lambda: node.cancel_count == 3, "invalid-joint cancel", 3)
                    wait_for(lambda: node.statuses and node.statuses[-1][1].get("reason") ==
                             "home_joint_state_invalid", "invalid-joint reason")
                    state_start = len(node.statuses)
                    node.terminal_gate.set()
                    wait_for(lambda: saw_state(node, "REARM_REQUIRED", state_start),
                             "invalid-joint terminal rearm")
                    node.invalid_joints = False
                    node.button = False
                    node.grip = 0.0
                    wait_for(lambda: node.latest_state() == "ARMED", "fourth rearm")

                    # Process shutdown during Home must request cancel and stop.
                    node.button = True
                    wait_for(lambda: len(node.goals) == 5, "shutdown Home goal", 3)
                    stop_before = node.stop_count
                    process.send_signal(signal.SIGINT)
                    wait_for(lambda: node.cancel_count == 4, "shutdown cancel request", 3)
                    wait_for(lambda: node.stop_count > stop_before, "shutdown stop")
                    node.terminal_gate.set()
                    wait_for(lambda: process.poll() is not None, "adapter shutdown", 5)
                    assert node.command_count == 0
                    wait_for(lambda: not any(name == "rm65_teleop_adapter"
                                             for name, _ in node.get_node_names_and_namespaces()),
                             "hardware-mode node cleanup")
                    dry_command = [str(EXECUTABLE), "--ros-args", "--params-file",
                                   str(PACKAGE / "config" / "dry_run.yaml")]
                    dry_process = subprocess.Popen(dry_command, stdout=log, stderr=subprocess.STDOUT)
                    try:
                        wait_for(lambda: any(name == "rm65_teleop_adapter"
                                             for name, _ in node.get_node_names_and_namespaces()),
                                 "dry-run node")
                        clients = node.get_client_names_and_types_by_node("rm65_teleop_adapter", "/")
                        assert not any("follow_joint_trajectory" in name for name, _ in clients)
                        assert node.count_publishers("/right/rm_driver/movep_canfd_cmd") == 0
                    finally:
                        if dry_process.poll() is None:
                            dry_process.send_signal(signal.SIGINT)
                            dry_process.wait(timeout=5)
                    print("synthetic Home: 5 goals, 4 cancels, 1 success, 0 Cartesian commands, 0 real publishers; dry-run has no Home client")
                except Exception:
                    print(log_path.read_text(encoding="utf-8"))
                    raise
                finally:
                    node.abort_gate.set()
                    if process.poll() is None:
                        process.send_signal(signal.SIGINT)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.terminate()
                            process.wait(timeout=5)
    finally:
        executor.shutdown(timeout_sec=5)
        thread.join(timeout=5)
        node.action.destroy()
        node.destroy_node()
        rclpy.shutdown()
        assert process.poll() is not None
