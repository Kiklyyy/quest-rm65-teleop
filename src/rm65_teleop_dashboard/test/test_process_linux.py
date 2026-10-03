"""Real process-tree tests use only sleeping Python fixtures, never ROS hardware."""
import os
import signal
import subprocess
import sys
import time
import pytest
from rm65_teleop_dashboard.process_environment import SubprocessRunner
from rm65_teleop_dashboard.process_manager import ProcessManager, LaunchRequest
from test_process_manager import preflight

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='POSIX process groups on Ubuntu')


def wait_until(predicate, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError('process fixture timeout')


@pytest.mark.parametrize('ignore,expected', [(False, 2), (True, 9)])
def test_real_owned_process_group_and_external_survives(ignore, expected):
    external = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    prefix = 'import signal; signal.signal(2,signal.SIG_IGN); signal.signal(15,signal.SIG_IGN); ' if ignore else ''
    code = prefix + 'import time; print("fixture-ready",flush=True); time.sleep(60)'
    actual = SubprocessRunner(os.environ)
    class FixtureRunner:
        def start(self, _):
            return actual.start((sys.executable, '-c', code))
    manager = ProcessManager(FixtureRunner(), grace_s=.15)
    try:
        manager.start(LaunchRequest(), preflight())
        handle = manager.handle
        wait_until(lambda: bool(handle.logs()))
        manager.stop()
        def stopped():
            manager.tick()
            return manager.handle is None
        wait_until(stopped)
        assert manager.state == 'STOPPED'
        assert external.poll() is None
        assert abs(manager.exit_code) == expected
    finally:
        if manager.handle:
            manager.handle.send_signal(signal.SIGKILL)
        external.terminate()
        external.wait(timeout=5)


def test_launch_leader_exit_cleans_owned_descendants():
    runner = SubprocessRunner(os.environ)
    code = ('import subprocess,sys; '
            'subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
            'print("parent-exit",flush=True)')
    class FixtureRunner:
        def start(self, _):
            return runner.start((sys.executable, '-c', code))
    manager = ProcessManager(FixtureRunner(), grace_s=.1)
    try:
        manager.start(LaunchRequest(), preflight())
        def stopped():
            manager.tick()
            return manager.handle is None
        wait_until(stopped)
        assert manager.state == 'FAILED'
        assert manager.exit_code == 0  # A launch exiting on its own is still unexpected.
    finally:
        if manager.handle:
            manager.handle.send_signal(signal.SIGKILL)
