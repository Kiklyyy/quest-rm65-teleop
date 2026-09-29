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
from rm_ros_interfaces.msg import Cartepos, Jointpos
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty, String

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "src" / "rm65_teleop_adapter"
EXECUTABLE = ROOT / "build" / "rm65_teleop_adapter" / "rm65_teleop_adapter_node"
PREFIX = "/test/home"


class SyntheticHome(Node):
    def __init__(self):
        super().__init__("rm_driver", namespace="/right")
        self.button_x = False
        self.button_a = False
        self.button_b = False
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
        self.x_inputs = self.create_publisher(
            OVR2ROSInputs, PREFIX + "/x_inputs", 10)
        self.robot = self.create_publisher(Pose, PREFIX + "/robot_pose", 10)
        self.joints = self.create_publisher(JointState, PREFIX + "/joints", 10)
        self.command_sub = self.create_subscription(
            Cartepos, PREFIX + "/movep_cmd", self._command, 10)
        self.movej_sub = self.create_subscription(
            Jointpos, PREFIX + "/movej_cmd", lambda _: None, 10)
        self.stop_sub = self.create_subscription(
            Empty, PREFIX + "/stop", self._stop, 10)
        self.status_sub = self.create_subscription(
            String, "/right/rm65_teleop/status", self._status, 10)
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
        inputs.button_upper = self.button_b
        inputs.button_lower = self.button_a
        inputs.press_middle = self.grip
        self.inputs.publish(inputs)
        x_inputs = OVR2ROSInputs()
        x_inputs.button_lower = self.button_x
        self.x_inputs.publish(x_inputs)
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
    controller = Node("rm_control", namespace="/right")
    controller.create_publisher(Jointpos, PREFIX + "/movej_cmd", 10)
    controller.create_subscription(Empty, PREFIX + "/stop", lambda _: None, 10)
    node.action = ActionServer(
        controller, FollowJointTrajectory, PREFIX + "/action",
        execute_callback=node._execute,
        goal_callback=node._goal,
        cancel_callback=node._cancel,
        callback_group=ReentrantCallbackGroup(),
    )
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    executor.add_node(controller)
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
                "quest_right_x_inputs_topic": PREFIX + "/x_inputs",
                "robot_pose_topic": PREFIX + "/robot_pose",
                "joint_state_topic": PREFIX + "/joints",
                "command_topic": PREFIX + "/movep_cmd",
                "home_movej_topic": PREFIX + "/movej_cmd",
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
                    wait_for(lambda: node.statuses[-1][1].get("command_path_ready"),
                             "Home topology command path", 5)
                    wait_for(lambda: node.statuses[-1][1].get("home_command_path_ready"),
                             "Home joint and stop path", 5)
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

                    def verify_successful_preset(button_attr, label, expected_degrees):
                        setattr(node, button_attr, True)
                        expected_count = len(node.goals) + 1
                        wait_for(lambda: len(node.goals) == expected_count,
                                 f"{label} preset goal", 3)
                        wait_for(lambda: node.latest_state() == "HOMING",
                                 f"{label} preset HOMING")
                        wait_for(
                            lambda: node.statuses[-1][1].get(
                                "joint_preset_selection") == label,
                            f"{label} preset status")
                        final_positions = node.goals[-1].trajectory.points[-1].positions
                        for actual, degrees in zip(final_positions, expected_degrees):
                            assert math.isclose(actual, math.radians(degrees), abs_tol=1e-9)
                        state_start = len(node.statuses)
                        node.terminal_gate.set()
                        wait_for(lambda: saw_state(node, "REARM_REQUIRED", state_start),
                                 f"{label} preset success")
                        setattr(node, button_attr, False)
                        wait_for(lambda: node.latest_state() == "ARMED",
                                 f"{label} preset release rearm")

                    verify_successful_preset(
                        "button_x", "X_FIRST",
                        [69.095, -32.717, 95.243, 34.124, 37.393, 159.266])
                    verify_successful_preset(
                        "button_a", "A_SECOND",
                        [83.357, 24.735, 67.241, -2.984, 73.23, -106.441])
                    node.goals.clear()
                    node.cancel_count = 0
                    node.stop_count = 0

                    # A short B hold cannot create a goal.
                    node.button_b = True
                    time.sleep(0.7)
                    assert len(node.goals) == 0
                    wait_for(lambda: len(node.goals) == 1, "first Home goal", 3)
                    wait_for(lambda: node.latest_state() == "HOMING", "first HOMING")
                    first_goal = node.goals[0]
                    assert first_goal.trajectory.joint_names == [f"joint{i}" for i in range(1, 7)]
                    points = first_goal.trajectory.points
                    assert len(points) == 4  # RealMan requires its >3-point spline branch.
                    expected_degrees = [
                        101.488, 45.519, 51.837, 0.307, 81.795, -170.454]
                    current_radians = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
                    assert all(math.isclose(a, c, abs_tol=1e-9)
                               for a, c in zip(points[0].positions, current_radians))
                    actual_positions = points[-1].positions
                    for actual, degrees in zip(actual_positions, expected_degrees):
                        assert math.isclose(actual, math.radians(degrees), abs_tol=1e-9)
                    times = []
                    for point in points:
                        assert len(point.positions) == len(point.velocities) == \
                            len(point.accelerations) == 6
                        assert all(math.isfinite(x) for values in
                                   (point.positions, point.velocities, point.accelerations)
                                   for x in values)
                        times.append(point.time_from_start.sec +
                                     point.time_from_start.nanosec * 1e-9)
                    assert times[0] == 0.0
                    assert times == sorted(times) and len(set(times)) == 4
                    duration = times[-1]
                    assert max(abs(a - c) for a, c in zip(actual_positions, current_radians)) <= \
                        duration * math.radians(50.0) / 1.5 + 1e-8
                    node.grip = 1.0
                    node.quest_x = 0.01
                    time.sleep(0.3)
                    assert node.command_count == 0
                    assert node.latest_state() == "HOMING"

                    # Cancel is requested immediately; the action result is deliberately held back.
                    state_start = len(node.statuses)
                    stop_before = node.stop_count
                    node.button_b = False
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
                    node.button_b = True
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
                    node.button_b = False
                    node.grip = 0.0
                    wait_for(lambda: node.latest_state() == "ARMED", "second rearm")
                    node.button_b = True
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
                    node.button_b = False
                    node.grip = 0.0
                    wait_for(lambda: node.latest_state() == "ARMED", "third rearm")
                    node.button_b = True
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
                    node.button_b = False
                    node.grip = 0.0
                    wait_for(lambda: node.latest_state() == "ARMED", "fourth rearm")

                    # Process shutdown during Home must request cancel and stop.
                    node.button_b = True
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
                    print("LAST STATUS", node.statuses[-1] if node.statuses else None)
                    for topic in (PREFIX + "/movej_cmd", PREFIX + "/action/_action/status"):
                        print("GRAPH", topic, [(x.node_name, x.node_namespace, x.topic_type)
                                               for x in node.get_publishers_info_by_topic(topic)])
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
        controller.destroy_node()
        node.destroy_node()
        rclpy.shutdown()
        assert process.poll() is not None


def test_command_path_ownership_probe():
    """A fake right driver/controller graph exercises endpoint ownership without goals."""
    assert os.environ.get("ROS_DOMAIN_ID") == "143"
    assert os.environ.get("ROS_LOCALHOST_ONLY") == "1"
    rclpy.init()
    driver = SyntheticHome()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(driver)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    controller = None
    action = None
    unknown = None
    duplicate = None
    cross_driver = None
    cross_controller = None
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="home_graph_") as temp:
            override_path = Path(temp) / "override.yaml"
            log_path = Path(temp) / "adapter.log"
            override_path.write_text(yaml.safe_dump({"rm65_teleop_adapter": {
                "ros__parameters": {
                    "target_topic": PREFIX + "/target",
                    "quest_pose_topic": PREFIX + "/quest_pose",
                    "inputs_topic": PREFIX + "/inputs",
                    "quest_right_x_inputs_topic": PREFIX + "/x_inputs",
                    "robot_pose_topic": PREFIX + "/robot_pose",
                    "joint_state_topic": PREFIX + "/joints",
                    "command_topic": PREFIX + "/movep_cmd",
                    "home_movej_topic": PREFIX + "/movej_cmd",
                    "stop_topic": PREFIX + "/stop",
                    "home_action_name": PREFIX + "/action",
                }}}), encoding="utf-8")
            with log_path.open("w", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [str(EXECUTABLE), "--ros-args", "--params-file",
                     str(PACKAGE / "config" / "hardware.yaml"),
                     "--params-file", str(override_path)],
                    stdout=log, stderr=subprocess.STDOUT)

                def paths():
                    if not driver.statuses:
                        return None
                    status = driver.statuses[-1][1]
                    return (status.get("command_path_ready"),
                            status.get("home_command_path_ready"))

                try:
                    wait_for(lambda: driver.latest_state() == "ARMED", "graph ARMED", 8)
                    wait_for(lambda: paths() == (True, False),
                             "driver-only Cartesian path")

                    controller = Node("rm_control", namespace="/right")
                    controller_movej = controller.create_publisher(
                        Jointpos, PREFIX + "/movej_cmd", 10)
                    controller.create_subscription(Empty, PREFIX + "/stop", lambda _: None, 10)
                    action = ActionServer(
                        controller, FollowJointTrajectory, PREFIX + "/action",
                        execute_callback=driver._execute,
                        goal_callback=driver._goal,
                        cancel_callback=driver._cancel,
                        callback_group=ReentrantCallbackGroup())
                    executor.add_node(controller)
                    wait_for(lambda: paths() == (True, True), "complete Home topology")

                    unknown = Node("unknown_command_source")
                    executor.add_node(unknown)
                    extra_movep = unknown.create_publisher(Cartepos, PREFIX + "/movep_cmd", 10)
                    wait_for(lambda: paths() == (False, False), "unknown movep publisher blocked")
                    unknown.destroy_publisher(extra_movep)
                    wait_for(lambda: paths() == (True, True), "movep path restored")

                    extra_movej = unknown.create_publisher(Jointpos, PREFIX + "/movej_cmd", 10)
                    wait_for(lambda: paths() == (True, False), "unknown movej publisher blocked")
                    unknown.destroy_publisher(extra_movej)
                    wait_for(lambda: paths() == (True, True), "movej path restored")

                    extra_stop = unknown.create_subscription(
                        Empty, PREFIX + "/stop", lambda _: None, 10)
                    wait_for(lambda: paths() == (False, False), "unknown stop subscriber blocked")
                    unknown.destroy_subscription(extra_stop)
                    wait_for(lambda: paths() == (True, True), "stop path restored")

                    # A cross-arm endpoint on the same test-only command topic
                    # must not be accepted as this right adapter's driver.
                    cross_driver = Node("rm_driver", namespace="/left")
                    executor.add_node(cross_driver)
                    cross_movep = cross_driver.create_subscription(
                        Cartepos, PREFIX + "/movep_cmd", lambda _: None, 10)
                    wait_for(lambda: paths() == (False, False),
                             "extra left driver endpoint blocked")
                    driver.destroy_subscription(driver.command_sub)
                    wait_for(lambda: paths() == (False, False),
                             "left driver cannot replace right driver")
                    cross_driver.destroy_subscription(cross_movep)
                    driver.command_sub = driver.create_subscription(
                        Cartepos, PREFIX + "/movep_cmd", driver._command, 10)
                    wait_for(lambda: paths() == (True, True),
                             "right driver endpoint restored")

                    cross_controller = Node("rm_control", namespace="/left")
                    executor.add_node(cross_controller)
                    cross_movej = cross_controller.create_publisher(
                        Jointpos, PREFIX + "/movej_cmd", 10)
                    wait_for(lambda: paths() == (True, False),
                             "extra left controller endpoint blocked")
                    controller.destroy_publisher(controller_movej)
                    wait_for(lambda: paths() == (True, False),
                             "left controller cannot replace right controller")
                    cross_controller.destroy_publisher(cross_movej)
                    controller_movej = controller.create_publisher(
                        Jointpos, PREFIX + "/movej_cmd", 10)
                    wait_for(lambda: paths() == (True, True),
                             "right controller endpoint restored")

                    duplicate = Node("rm_control", namespace="/right")
                    executor.add_node(duplicate)
                    wait_for(lambda: paths() == (False, False), "duplicate controller blocked")
                    # The initial driver-only phase covered a missing controller.
                    # Destroying duplicate same-name ROS nodes can leave endpoint
                    # identities UNKNOWN until the isolated graph is torn down.
                    assert driver.goals == []
                    assert driver.command_count == 0
                except Exception:
                    print("LAST STATUS", driver.statuses[-1] if driver.statuses else None)
                    for topic in (PREFIX + "/movej_cmd", PREFIX + "/action/_action/status"):
                        print("GRAPH", topic, [(x.node_name, x.node_namespace, x.topic_type)
                                               for x in driver.get_publishers_info_by_topic(topic)])
                    print(log_path.read_text(encoding="utf-8"))
                    raise
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=5)
        executor.shutdown(timeout_sec=5)
        thread.join(timeout=5)
        if action is not None:
            action.destroy()
        if duplicate is not None:
            duplicate.destroy_node()
        if controller is not None:
            controller.destroy_node()
        if unknown is not None:
            unknown.destroy_node()
        driver.destroy_node()
        rclpy.shutdown()
