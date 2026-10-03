from rm65_teleop_dashboard.models import SystemSnapshot
from rm65_teleop_dashboard.process_manager import LaunchRequest
from rm65_teleop_dashboard.runtime_observer import GraphEvidence
from rm65_teleop_dashboard.runtime_service import RuntimeService
from test_process_manager import FakeRunner


def service(graph=GraphEvidence()):
    return RuntimeService(lambda: graph, SystemSnapshot, {'ROS_DOMAIN_ID': '42'},
                          runner=FakeRunner(), packages=(True, True))


def test_worker_rechecks_current_facts_instead_of_ui_result():
    runtime = service(GraphEvidence(tcp_port_free=False))
    runtime.request_start(LaunchRequest())
    runtime.cycle()
    assert not runtime.system.runner.calls
    assert 'START_BLOCKED' in runtime.snapshot().events[-1].message


def test_stop_and_close_ignore_external_processes():
    runtime = service(GraphEvidence(nodes=('/left/rm_driver', '/right/rm_driver')))
    runtime.request_stop()
    runtime.cycle()
    runtime.close()
    assert not runtime.system.runner.calls
    assert runtime.snapshot().components[1].ownership == 'External'


def test_start_stop_close_owned_handle_and_bounded_logs():
    runtime = service()
    runtime.request_start(LaunchRequest())
    runtime.cycle()
    assert runtime.snapshot().system.state == 'RUNNING'
    handle = runtime.system.handle
    runtime.request_stop()
    runtime.cycle()
    assert handle.signals == [2]
    handle.exit_code, handle.living = 0, False
    runtime.cycle()
    runtime.close()
    assert runtime.snapshot().system.state == 'STOPPED'


def test_demo_cannot_enqueue_real_start():
    runtime = RuntimeService.demo()
    runtime.request_start(LaunchRequest('hardware'))
    runtime.cycle()
    assert not runtime.snapshot().enabled
    assert runtime.system.handle is None


def test_stop_survives_graph_failure_and_full_start_queue():
    import pytest
    runtime = service()
    runtime.request_start(LaunchRequest())
    runtime.cycle()
    handle = runtime.system.handle
    for _ in range(30):
        runtime.request_start(LaunchRequest())
    def fail():
        raise RuntimeError('graph unavailable')
    runtime.graph_provider = fail
    runtime.request_stop()
    with pytest.raises(RuntimeError, match='graph unavailable'):
        runtime.cycle()
    assert handle.signals == [2]
    assert runtime._requests.empty()  # No delayed restart after a Stop.


def test_closing_app_stops_owned_group_even_without_ros_graph():
    runtime = service()
    runtime.request_start(LaunchRequest())
    runtime.cycle()
    handle = runtime.system.handle
    def stop(sig):
        handle.signals.append(sig)
        handle.exit_code, handle.living = 0, False
    handle.send_signal = stop
    def fail():
        raise RuntimeError('ROS context unavailable')
    runtime.graph_provider = fail
    runtime.start()
    runtime.close()
    assert handle.signals == [2]
    assert runtime.system.handle is None
    assert not runtime._thread.is_alive()


def test_close_without_worker_waits_and_escalates_owned_handle():
    runtime = service()
    runtime.system.grace_s = .01
    runtime.request_start(LaunchRequest())
    runtime.cycle()
    handle = runtime.system.handle
    def stop(sig):
        handle.signals.append(sig)
        if sig == 15:
            handle.exit_code, handle.living = -15, False
    handle.send_signal = stop
    runtime.close()
    assert handle.signals == [2, 15]
    assert runtime.system.handle is None


def test_repeated_observation_error_logs_once_and_recovers():
    runtime = service()
    runtime.observation_failed(RuntimeError('graph unavailable'))
    runtime.observation_failed(RuntimeError('graph unavailable'))
    assert sum('RUNTIME_OBSERVER_ERROR' in e.message for e in runtime.system.events) == 1
    assert not runtime.snapshot().facts.graph_ok
    runtime.cycle()
    assert runtime.system.error == ''
    assert sum('RUNTIME_OBSERVER_RECOVERED' in e.message for e in runtime.system.events) == 1
