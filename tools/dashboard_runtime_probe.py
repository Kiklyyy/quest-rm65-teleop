"""CI-only isolated Dry Run of the existing dual launch through the manager."""
import os
import time

assert os.environ.get('ROS_DOMAIN_ID') == '143', 'isolated domain required'
assert os.environ.get('ROS_LOCALHOST_ONLY') == '1', 'localhost isolation required'

from rm65_teleop_dashboard.models import SnapshotStore
from rm65_teleop_dashboard.ros_monitor import RosMonitorRuntime
from rm65_teleop_dashboard.process_manager import LaunchRequest, launch_command
from rm65_teleop_dashboard.runtime_observer import inspect_graph
from rm65_teleop_dashboard.runtime_service import RuntimeService


def wait_until(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.2)
    raise AssertionError('Dry Run lifecycle timeout')


store = SnapshotStore(domain_id='143')
monitor = RosMonitorRuntime(store)
runtime = RuntimeService(lambda: inspect_graph(monitor.node), store.snapshot, os.environ)
try:
    monitor.start()
    runtime.start()
    wait_until(lambda: runtime.snapshot().facts.environment_ok)
    assert runtime.snapshot().facts.tcp_port_free
    print('Command:', ' '.join(launch_command(LaunchRequest())))
    runtime.request_start(LaunchRequest())
    def adapters_online():
        snapshot = store.snapshot()
        assert runtime.snapshot().system.state != 'FAILED', runtime.snapshot().system_logs
        return all(a.status_health.state == 'ONLINE' and a.adapter.dry_run is True
                   for a in (snapshot.left, snapshot.right))
    wait_until(adapters_online)
    graph = inspect_graph(monitor.node)
    assert graph.tcp_listening
    assert not any(n in graph.nodes for n in ('/left/rm_driver', '/right/rm_driver',
        '/left/rm_control', '/right/rm_control', '/right_linkerhand'))
    topics = [name for name, _ in monitor.node.get_topic_names_and_types()]
    assert not any('movep_canfd' in name or 'movej_canfd' in name for name in topics)
    assert len(tuple(monitor.node.publishers)) == len(tuple(monitor.node.clients)) == len(tuple(monitor.node.services)) == 0
    assert len(tuple(monitor.node.subscriptions)) == 13
    assert runtime.snapshot().system.pid is not None
    print('Dry Run: both real adapters dry_run=true; no driver/control/hand or robot command topics')
    runtime.request_stop()
    wait_until(lambda: runtime.snapshot().system.state == 'STOPPED')
    wait_until(lambda: inspect_graph(monitor.node).tcp_port_free)
    print('Stop: owned launch group exited; TCP 10000 released')
finally:
    runtime.close()
    monitor.stop()
print('Runtime Dry Run smoke PASSED')
