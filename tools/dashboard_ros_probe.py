#!/usr/bin/python3
"""Isolated synthetic receive test. Never run on the hardware ROS domain.

Fixture publishers live outside the dashboard package and use ONLY its feedback
topics. This is test infrastructure, not a GUI feature or robot control source.
"""
import json
import math
import os
import time
from dataclasses import asdict

if os.environ.get('ROS_DOMAIN_ID') != '143' or os.environ.get('ROS_LOCALHOST_ONLY') != '1':
    raise SystemExit('Probe requires ROS_DOMAIN_ID=143 and ROS_LOCALHOST_ONLY=1')

import rclpy
from rclpy.context import Context
from rclpy.node import Node
from rm65_teleop_dashboard.demo_data import demo_snapshot
from rm65_teleop_dashboard.models import EventLogger, SnapshotStore
from rm65_teleop_dashboard.ros_monitor import RosMonitorRuntime, TOPICS


def main():
    fixture_context = Context()
    rclpy.init(context=fixture_context)
    fixture = Node('dashboard_receive_fixture', context=fixture_context, enable_rosout=False)
    store = SnapshotStore(domain_id='143')
    monitor = RosMonitorRuntime(store)
    pubs, messages, periods, due = {}, {}, {}, {}
    demo = demo_snapshot(1.0, domain_id='143')
    for key, (topic, msg_type) in TOPICS.items():
        pubs[key] = fixture.create_publisher(msg_type, topic, 10)
        message = msg_type()
        stream = key.split('.')[-1]
        if stream in ('quest', 'target', 'robot'):
            pose = message if stream == 'robot' else message.pose
            pose.position.x, pose.position.y, pose.position.z = (.42, -.22, .55)
            pose.orientation.w = 1.0
        elif stream == 'inputs':
            message.press_middle, message.press_index = .7, .2
            message.button_lower, message.button_upper = True, False
        elif stream == 'joints':
            message.name = ['joint3', 'joint1', 'joint6', 'joint2', 'joint5', 'joint4']
            message.position = [.3, .1, .6, .2, .5, .4]
        elif stream == 'status':
            message.data = json.dumps(asdict(getattr(demo, key.split('.')[0]).adapter))
        else:
            message.data = json.dumps(asdict(demo.linkerhand))
        messages[key] = message
        periods[key] = (1 / 198 if stream in ('robot', 'joints') else
                        1 / 72 if stream in ('quest', 'inputs') else
                        1 / 50 if stream == 'target' else .1)
        due[key] = time.monotonic()
    try:
        monitor.start()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            for key in messages:
                if now >= due[key]:
                    pubs[key].publish(messages[key])
                    due[key] = now + periods[key]
            time.sleep(.001)
        snapshot = store.snapshot()
        for side in ('left', 'right'):
            arm = getattr(snapshot, side)
            controller = getattr(snapshot, side + '_controller')
            assert arm.robot_health.state == arm.joints_health.state == 'ONLINE'
            assert arm.target_health.state == arm.status_health.state == 'ONLINE'
            assert arm.robot_pose.position == arm.target_pose.position == (.42, -.22, .55)
            assert all(math.isclose(value, math.degrees((i + 1) * .1))
                       for i, value in enumerate(arm.joints_deg))
            assert controller.pose_health.state == controller.inputs_health.state == 'ONLINE'
            assert math.isclose(controller.grip, .7, abs_tol=1e-6)
            assert math.isclose(controller.trigger, .2, abs_tol=1e-6)
            assert controller.button_lower is True and controller.button_upper is False
            assert 45 < controller.pose_health.hz < 90
            assert 100 < arm.robot_health.hz < 230
        assert snapshot.left.adapter.state == 'ACTIVE'
        assert snapshot.right.adapter.state == 'ARMED'
        assert snapshot.linkerhand.health.state == 'ONLINE'
        assert len(snapshot.linkerhand.target) == len(snapshot.linkerhand.actual) == 7
        assert not tuple(monitor.node.publishers)
        assert not tuple(monitor.node.services)
        assert not tuple(monitor.node.clients)
        logger = EventLogger()
        first = logger.update(snapshot)
        assert logger.update(snapshot) == first
        messages['right.status'].data = '{bad JSON'
        for _ in range(20):
            pubs['right.status'].publish(messages['right.status'])
            time.sleep(.01)
        assert store.snapshot().right.adapter.state == 'DATA_ERROR'
        time.sleep(2.1)
        expired = store.snapshot()
        assert expired.right.adapter.dry_run is None
        assert expired.left.status_health.state == expired.right.status_health.state == 'OFFLINE'
        assert expired.linkerhand.state == 'OFFLINE'
        print('PASS: 13 real ROS subscriptions; shuffled six joints; 72/198 Hz receipt; '
              'malformed JSON; stale suppression; zero output endpoints; deduplicated events.')
    finally:
        monitor.stop()
        fixture.destroy_node()
        rclpy.shutdown(context=fixture_context)
    assert not monitor.thread.is_alive()
    print('PASS: executor/thread/context clean shutdown.')


if __name__ == '__main__':
    main()
