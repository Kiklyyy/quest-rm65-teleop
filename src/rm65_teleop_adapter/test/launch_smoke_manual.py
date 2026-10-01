"""Manual isolated launch smoke; never select hardware mode."""

import json
import os
from pathlib import Path
import signal
import subprocess
import time

import rclpy
from quest2ros.msg import OVR2ROSInputs
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String


def wait_for(executor, predicate, timeout=12.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        executor.spin_once(timeout_sec=0.1)
        if predicate():
            return
    raise AssertionError("timed out waiting for isolated launch observation")


def run_case(enabled):
    case = "on" if enabled else "off"
    logfile = Path(f"/tmp/right_linkerhand_launch_smoke_{case}.log")
    command = [
        "ros2", "launch", "rm65_teleop_adapter", "right_quest_teleop.launch.py",
        "mode:=dry_run", f"start_linkerhand:={'true' if enabled else 'false'}",
        "start_tcp:=false", "start_bridge:=false", "start_status:=false",
        "use_rviz:=false",
    ]
    with logfile.open("w") as output:
        process = subprocess.Popen(
            command, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True)
        peer = rclpy.create_node(f"hand_smoke_peer_{case}")
        executor = SingleThreadedExecutor()
        executor.add_node(peer)
        received = []
        peer.create_subscription(
            String, "/right/linkerhand/status",
            lambda msg: received.append(json.loads(msg.data)), 10)
        pub = peer.create_publisher(OVR2ROSInputs, "/q2r_right_hand_inputs", 10)
        try:
            wait_for(executor, lambda: "/rm65_teleop_adapter" in
                     ["/" + name for name in peer.get_node_names()])
            if enabled:
                wait_for(executor, lambda: "/right_linkerhand" in
                         ["/" + name for name in peer.get_node_names()])
                wait_for(executor, lambda: pub.get_subscription_count() > 0)
                wait_for(executor, lambda: any(
                    s["target"] is None and s["hand_toggle_state"] == "OPEN"
                    for s in received))
                msg = OVR2ROSInputs()
                msg.press_index = 1.0
                until = time.monotonic() + 5.0
                while time.monotonic() < until:
                    pub.publish(msg)
                    executor.spin_once(timeout_sec=0.1)
                    if any(s["target"] == [73, 0, 0, 0, 0, 0, 156]
                           and s["dry_run"] and s["actual"] is None
                           for s in received):
                        break
                else:
                    raise AssertionError("no hand dry-run target/status")
                msg.press_index = 0.0
                pub.publish(msg)
                wait_for(executor, lambda: received[-1]["trigger_armed"])
                assert received[-1]["target"] == [73, 0, 0, 0, 0, 0, 156]
                msg.press_index = 1.0
                pub.publish(msg)
                wait_for(executor, lambda: received[-1]["target"] ==
                         [73, 0, 255, 255, 255, 255, 156])
            else:
                for _ in range(10):
                    executor.spin_once(timeout_sec=0.1)
                assert "/right_linkerhand" not in [
                    "/" + name for name in peer.get_node_names()]
                assert not peer.get_publishers_info_by_topic("/right/linkerhand/status")
            assert not peer.get_publishers_info_by_topic(
                "/right/rm_driver/movep_canfd_cmd")
            print(f"launch {case}: PASS; hand status samples={len(received)}")
        finally:
            executor.remove_node(peer)
            peer.destroy_node()
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    print(f"launch {case} log: {logfile}")


if __name__ == "__main__":
    rclpy.init()
    try:
        run_case(False)
        run_case(True)
    finally:
        rclpy.shutdown()
