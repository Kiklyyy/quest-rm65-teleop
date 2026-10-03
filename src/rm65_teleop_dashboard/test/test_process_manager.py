"""Process lifecycle contracts, tested without ROS or hardware."""
import ast
from pathlib import Path
import pytest

from rm65_teleop_dashboard.process_manager import LaunchRequest, launch_command
from rm65_teleop_dashboard.preflight import Confirmation, PreflightFacts, evaluate_preflight


@pytest.mark.parametrize('mode,enabled', [('dry_run', 'false'), ('hardware', 'true')])
def test_commands_follow_actual_dual_launch_contract(mode, enabled):
    command = launch_command(LaunchRequest(mode=mode))
    assert command[:4] == ('ros2', 'launch', 'rm65_teleop_adapter', 'dual_quest_teleop.launch.py')
    args = dict(value.split(':=') for value in command[4:])
    launch = Path(__file__).parents[2] / 'rm65_teleop_adapter/launch/dual_quest_teleop.launch.py'
    tree = ast.parse(launch.read_text(encoding='utf-8'))
    declared = {node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == 'DeclareLaunchArgument'}
    assert set(args) <= declared
    assert args['mode'] == mode
    assert args['start_drivers'] == args['start_controls'] == enabled
    assert args['start_linkerhand'] == args['linkerhand_connect_only'] == 'false'
    assert args['motion_profile'] == 'safe'


@pytest.mark.parametrize('mode,profile', [('invalid', 'safe'), ('hardware', 'fast')])
def test_invalid_launch_selections_rejected(mode, profile):
    with pytest.raises(ValueError):
        launch_command(LaunchRequest(mode, profile))


class FakeHandle:
    pid = 1234
    exit_code = None
    living = True

    def __init__(self):
        self.signals = []

    def poll(self):
        return self.exit_code

    def alive(self):
        return self.living

    def send_signal(self, sig):
        self.signals.append(sig)

    def logs(self):
        return ('launch output',)


class FakeRunner:
    def __init__(self, error=False):
        self.calls = []
        self.error = error
        self.handle = FakeHandle()

    def start(self, command):
        self.calls.append(command)
        if self.error:
            raise OSError('executable unavailable')
        return self.handle


def preflight(mode='dry_run', **kwargs):
    return evaluate_preflight(PreflightFacts(environment_ok=True, hardware_packages=True,
        graph_ok=True, process_scan_ok=True, tcp_port_free=True, **kwargs), mode)


def manager(runner=None):
    from rm65_teleop_dashboard.process_manager import ProcessManager
    return ProcessManager(runner or FakeRunner(), grace_s=1)


def test_start_duplicate_and_pid_does_not_mean_ready():
    pm = manager()
    pm.start(LaunchRequest(), preflight(), now=0)
    assert pm.state == 'RUNNING'
    assert pm.handle.pid == 1234
    assert not pm.ready
    with pytest.raises(RuntimeError, match='already'):
        pm.start(LaunchRequest(), preflight(), now=0)
    assert len(pm.runner.calls) == 1


def test_start_failure_and_unexpected_exit():
    pm = manager(FakeRunner(error=True))
    pm.start(LaunchRequest(), preflight(), now=0)
    assert pm.state == 'FAILED'
    assert 'PROCESS_START_FAILED' in pm.events[-1].message
    pm = manager()
    pm.start(LaunchRequest(), preflight(), now=0)
    pm.handle.exit_code, pm.handle.living = 7, False
    pm.tick(now=1)
    assert pm.state == 'FAILED' and pm.exit_code == 7
    assert any('PROCESS_EXITED' in e.message for e in pm.events)


def test_stop_escalates_only_owned_group_and_emits_once():
    import signal
    pm = manager()
    pm.stop(now=0)  # external graph without a handle is never signalled
    assert not pm.runner.calls
    pm.start(LaunchRequest(), preflight(), now=0)
    handle = pm.handle
    pm.stop(now=1)
    pm.stop(now=1.5)
    assert handle.signals == [signal.SIGINT]
    pm.tick(now=2.1)
    assert handle.signals == [signal.SIGINT, signal.SIGTERM]
    pm.tick(now=3.2)
    assert handle.signals[-1] == 9
    handle.exit_code, handle.living = -9, False
    pm.tick(now=3.3)
    assert pm.state == 'STOPPED'
    pm.tick(now=4)
    assert sum('SYSTEM_STOPPED' in e.message for e in pm.events) == 1


def test_hardware_preflight_and_manual_gate_enforced_below_ui():
    pm = manager()
    with pytest.raises(RuntimeError):
        pm.start(LaunchRequest('hardware'), preflight('hardware'), now=0)
    with pytest.raises(RuntimeError):
        pm.start(LaunchRequest('hardware'), preflight('hardware', duplicate_driver=True),
                 Confirmation(True, True, True), now=0)
    assert not pm.runner.calls
    pm.start(LaunchRequest('hardware'), preflight('hardware'), Confirmation(True, True, True), now=0)
    assert pm.state == 'RUNNING'


def test_matching_preflight_mode_and_readiness_event_dedup():
    pm = manager()
    with pytest.raises(RuntimeError):
        pm.start(LaunchRequest('hardware'), preflight(), Confirmation(True, True, True), now=0)
    pm.start(LaunchRequest(), preflight(), now=0)
    pm.set_ready(True)
    pm.set_ready(True)
    assert sum('SYSTEM_READY' in e.message for e in pm.events) == 1


def test_hand_is_separate_opt_in_and_hardware_requires_risk_confirmation():
    request = LaunchRequest('hardware', component='hand')
    command = launch_command(request)
    assert command[:4] == ('ros2', 'run', 'rm65_teleop_adapter', 'right_linkerhand_node')
    assert 'dry_run:=false' in command and 'hardware_write_enabled:=true' in command
    result = evaluate_preflight(PreflightFacts(environment_ok=True, hand_sdk_ok=True, graph_ok=True,
        process_scan_ok=True, duplicate_driver=True, stack_running=True), 'hardware', 'hand')
    assert result.allowed
    assert not result.can_start(Confirmation(True, True, True))
    assert result.can_start(Confirmation(True, True, True, True))
    pm = manager()
    pm.start(request, result, Confirmation(True, True, True, True), now=0)
    assert pm.runner.calls == [command]


def test_dry_run_hand_never_enables_hardware():
    command = launch_command(LaunchRequest(component='hand'))
    assert 'dry_run:=true' in command and 'hardware_write_enabled:=false' in command
