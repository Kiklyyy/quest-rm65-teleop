"""Real Humble node graph/lifecycle test, isolated from hardware."""
import os
import time

import pytest


def test_monitor_has_only_subscriptions_and_shuts_down():
    pytest.importorskip('rclpy')
    pytest.importorskip('quest2ros.msg')
    os.environ['ROS_DOMAIN_ID'] = '143'
    os.environ['ROS_LOCALHOST_ONLY'] = '1'
    from rm65_teleop_dashboard.models import SnapshotStore
    from rm65_teleop_dashboard.ros_monitor import RosMonitorRuntime, TOPICS
    runtime = RosMonitorRuntime(SnapshotStore(domain_id='143'))
    try:
        runtime.start()
        assert len(tuple(runtime.node.subscriptions)) == len(TOPICS) == 13
        assert not tuple(runtime.node.publishers)
        assert not tuple(runtime.node.services)
        assert not tuple(runtime.node.clients)
        time.sleep(0.05)
    finally:
        runtime.stop()
    assert not runtime.thread.is_alive()
    runtime.stop()  # Repeated close is harmless.
