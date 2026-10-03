"""Software process ownership. This layer never creates ROS endpoints."""
from dataclasses import dataclass
from collections import deque
import signal
import time
from .models import EventRecord
from .preflight import Confirmation

SIGKILL = getattr(signal, 'SIGKILL', 9)  # Linux lifecycle, portable fake-runner tests.


@dataclass(frozen=True)
class LaunchRequest:
    mode: str = 'dry_run'
    profile: str = 'safe'
    component: str = 'system'


def launch_command(request):
    if (request.mode not in ('dry_run', 'hardware') or request.profile not in ('safe', 'normal')
            or request.component not in ('system', 'hand')):
        raise ValueError('Expected dry_run/hardware and safe/normal')
    hardware = str(request.mode == 'hardware').lower()
    if request.component == 'hand':
        return ('ros2', 'run', 'rm65_teleop_adapter', 'right_linkerhand_node', '--ros-args',
                '-r', '__node:=right_linkerhand', '-p', f'dry_run:={str(request.mode != "hardware").lower()}',
                '-p', f'hardware_write_enabled:={hardware}', '-p', 'connect_only:=false')
    return ('ros2', 'launch', 'rm65_teleop_adapter', 'dual_quest_teleop.launch.py',
            f'mode:={request.mode}', f'motion_profile:={request.profile}',
            f'start_drivers:={hardware}', f'start_controls:={hardware}',
            'start_tcp:=true', 'start_bridges:=true', 'start_status:=true',
            'start_linkerhand:=false', 'linkerhand_connect_only:=false',
            'use_right_rviz:=false', 'use_left_rviz:=false')


class ProcessManager:
    """Single-worker state machine; runner injection makes lifecycle tests deterministic.

    RUNNING describes the owned process only. Readiness is separate ROS evidence.
    Stopping never takes a PID supplied by the graph or by the user.
    """
    def __init__(self, runner, grace_s=5.0, source='system'):
        self.runner, self.grace_s, self.source = runner, grace_s, source
        self.handle = None
        self.state = 'STOPPED'
        self.request = LaunchRequest()
        self.exit_code = None
        self.ready = False
        self.events = deque(maxlen=500)
        self.error = ''
        self._stop_stage = 0
        self._deadline = 0
        self._failed = False
        self._last_logs = ()

    def event(self, code, detail='', level='INFO'):
        self.events.append(EventRecord(time.time(), level, self.source, f'{code} · {detail}'))

    def start(self, request, preflight, confirmation=Confirmation(), now=None):
        if self.handle is not None:
            raise RuntimeError('Process group already owned; stop it before starting again')
        if (preflight.mode != request.mode or preflight.component != request.component
                or not preflight.can_start(confirmation)):
            raise RuntimeError('启动检查或人工确认尚未通过')
        argv = launch_command(request)
        self.request = request
        self.error, self.exit_code, self.ready = '', None, False
        self._failed = False
        self._last_logs = ()
        self.event('SYSTEM_START_REQUESTED', f'{request.mode} / {request.profile}')
        self.state = 'STARTING'
        try:
            self.handle = self.runner.start(argv)
            self.state = 'RUNNING'
            self.event('PROCESS_STARTED', f'PID {self.handle.pid}; awaiting ROS evidence')
        except (OSError, RuntimeError) as exc:
            self.state, self.error = 'FAILED', str(exc)
            self.event('PROCESS_START_FAILED', self.error, 'ERROR')

    def set_ready(self, ready):
        ready = bool(ready and self.state == 'RUNNING')
        if ready and not self.ready:
            self.event('SYSTEM_READY', '所需组件与实时输入已就绪；不代表硬件安全认证')
        self.ready = ready

    def stop(self, now=None):
        if self.handle is None or self.state == 'STOPPING':
            return
        self.state, self.ready = 'STOPPING', False
        self._stop_stage = 1
        self._deadline = (time.monotonic() if now is None else now) + self.grace_s
        self.event('SYSTEM_STOP_REQUESTED', '仅停止本软件拥有的进程组')
        self.handle.send_signal(signal.SIGINT)

    def tick(self, now=None):
        if self.handle is None:
            return
        now = time.monotonic() if now is None else now
        code = self.handle.poll()
        if code is not None and self.exit_code is None:
            self.exit_code = code
            self.event('PROCESS_EXITED', f'exit code {code}',
                       'INFO' if self.state == 'STOPPING' else 'ERROR')
            if self.state != 'STOPPING':
                self._failed, self.error = True, f'进程意外退出 ({code})'
                # Also clean up descendants when the launch leader exits early.
                self.stop(now)
        if not self.handle.alive():
            self._last_logs = self.handle.logs()
            self.handle = None
            self.state = 'FAILED' if self._failed else 'STOPPED'
            self.ready = False
            self.event('SYSTEM_STOPPED', '本软件进程组已退出')
        elif self.state == 'STOPPING' and now >= self._deadline:
            if self._stop_stage < 3:
                self._stop_stage += 1
                self.handle.send_signal(signal.SIGTERM if self._stop_stage == 2 else SIGKILL)
                self._deadline = now + self.grace_s
                self.event('STOP_ESCALATED', f'stage {self._stop_stage}', 'WARN')

    def logs(self):
        return self.handle.logs() if self.handle else self._last_logs
