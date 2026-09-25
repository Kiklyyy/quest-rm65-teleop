"""Synthetic command graph: the left adapter rejects right-side owners."""

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time

import pytest
import rclpy
import yaml
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rm_ros_interfaces.msg import Cartepos
from std_msgs.msg import Empty, String


ROOT = Path(__file__).resolve().parents[3]
ADAPTER = ROOT / "build/rm65_teleop_adapter/rm65_teleop_adapter_node"
CONFIG = ROOT / "src/rm65_teleop_adapter/config/left_dry_run.yaml"
PREFIX = "/test/left_ownership"


def wait_for(predicate, label, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(f"timeout waiting for {label}")


def test_left_adapter_rejects_right_driver_and_extra_cross_arm_endpoint():
    assert os.environ.get("ROS_DOMAIN_ID") == "143"
    assert os.environ.get("ROS_LOCALHOST_ONLY") == "1"
    rclpy.init()
    probe = Node("left_ownership_probe")
    right = Node("rm_driver", namespace="/right")
    left = Node("rm_driver", namespace="/left")
    statuses = []
    probe.create_subscription(
        String, PREFIX + "/status",
        lambda msg: statuses.append(json.loads(msg.data)), 10)
    right_movep = right.create_subscription(
        Cartepos, PREFIX + "/movep", lambda _: None, 10)
    right_stop = right.create_subscription(
        Empty, PREFIX + "/stop", lambda _: None, 10)
    executor = MultiThreadedExecutor(num_threads=3)
    for node in (probe, right, left):
        executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="left_ownership_") as temp:
            override = Path(temp) / "override.yaml"
            log_path = Path(temp) / "adapter.log"
            # Hardware mode exists only inside this isolated test graph and
            # publishes to /test/*, never to a real /left/rm_driver topic.
            override.write_text(yaml.safe_dump({
                "left_rm65_teleop_adapter": {"ros__parameters": {
                    "dry_run": False,
                    "hardware_write_enabled": True,
                    "mapping_verified": True,
                    "command_topic": PREFIX + "/movep",
                    "stop_topic": PREFIX + "/stop",
                    "status_topic": PREFIX + "/status",
                    "preview_topic": PREFIX + "/preview",
                    "clear_fault_service": PREFIX + "/clear_fault",
                }}
            }), encoding="utf-8")
            with log_path.open("w", encoding="utf-8") as log:
                process = subprocess.Popen([
                    str(ADAPTER), "--ros-args",
                    "-r", "__node:=left_rm65_teleop_adapter",
                    "--params-file", str(CONFIG),
                    "--params-file", str(override),
                ], stdout=log, stderr=subprocess.STDOUT)
                try:
                    wait_for(lambda: bool(statuses), "adapter status")
                    wait_for(lambda: statuses[-1]["command_path_ready"] is False,
                             "right driver rejected")
                    left_movep = left.create_subscription(
                        Cartepos, PREFIX + "/movep", lambda _: None, 10)
                    left_stop = left.create_subscription(
                        Empty, PREFIX + "/stop", lambda _: None, 10)
                    wait_for(lambda: statuses[-1]["command_path_ready"] is False,
                             "extra right driver rejected")
                    right.destroy_subscription(right_movep)
                    right.destroy_subscription(right_stop)
                    wait_for(lambda: statuses[-1]["command_path_ready"] is True,
                             "sole configured left driver accepted")
                    right_movep = right.create_subscription(
                        Cartepos, PREFIX + "/movep", lambda _: None, 10)
                    wait_for(lambda: statuses[-1]["command_path_ready"] is False,
                             "cross-arm publisher/subscriber rejected again")
                    assert probe.count_publishers("/left/rm_driver/movep_canfd_cmd") == 0
                    assert probe.count_publishers("/left/rm_driver/move_stop_cmd") == 0
                    assert all(s["home_action_state"] == "DISABLED" for s in statuses)
                    left.destroy_subscription(left_movep)
                    left.destroy_subscription(left_stop)
                except Exception:
                    print(log_path.read_text(encoding="utf-8"))
                    print("last status", statuses[-1] if statuses else None)
                    raise
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=5)
        executor.shutdown(timeout_sec=5)
        thread.join(timeout=5)
        for node in (probe, right, left):
            node.destroy_node()
        rclpy.shutdown()
