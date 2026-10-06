"""Ubuntu environment discovery and narrowly owned POSIX process groups."""
from collections import deque
from pathlib import Path
import ast
import os
import shlex
import subprocess
import sys
import threading


def discover_setup(environ=None):
    env = os.environ if environ is None else environ
    explicit = env.get('TELEOP_WORKSPACE_SETUP')
    if explicit:
        path = Path(explicit).expanduser().absolute()
        if not path.is_file():
            raise RuntimeError(f'Workspace setup missing: {path}')
        return path
    prefixes = [Path(p) for p in env.get('AMENT_PREFIX_PATH', '').split(os.pathsep) if p]
    # Installed Python modules retain their prefix even with ament symlink-install.
    prefixes += list(Path(__file__).absolute().parents)
    for prefix in prefixes:
        if str(prefix).startswith('/opt/ros/'):
            continue
        for candidate in (prefix / 'setup.bash', prefix.parent / 'setup.bash'):
            if candidate.is_file():
                return candidate.absolute()
    return None


def sourced_command(command, setup=None):
    # Never interpolate unquoted user paths or arguments into bash.
    parts = ['source /opt/ros/humble/setup.bash']
    if setup:
        parts.append(f'source {shlex.quote(str(setup))}')
    parts.append('export PATH=/usr/bin:/bin:$PATH')
    parts.append('exec ' + shlex.join(command))
    return ('/bin/bash', '-lc', ' && '.join(parts))


def load_environment(setup=None, environ=None):
    if sys.platform != 'linux':
        raise RuntimeError('ROS lifecycle requires Ubuntu 22.04 / system Python')
    env = dict(os.environ if environ is None else environ)
    setup = setup or discover_setup(env)
    result = subprocess.run(sourced_command(('/usr/bin/env', '-0'), setup), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12, check=True)
    loaded = dict(item.decode('utf-8').split('=', 1) for item in result.stdout.split(b'\0') if b'=' in item)
    # The domain selected for the monitor must also be used by every owned launch.
    loaded['ROS_DOMAIN_ID'] = env.get('ROS_DOMAIN_ID', '0')
    loaded['TELEOP_DASHBOARD_ENV_READY'] = '1'
    return loaded


def environment_packages(environ):
    """Read installed package markers/launch files, without importing drivers."""
    prefixes = [Path(p) for p in environ.get('AMENT_PREFIX_PATH', '').split(os.pathsep) if p]
    def package(name, relative=None):
        for prefix in prefixes:
            if (prefix / 'share/ament_index/resource_index/packages' / name).is_file():
                return not relative or (prefix / 'share' / name / relative).is_file()
        return False
    software = all(package(n) for n in ('quest2ros', 'ros_tcp_endpoint', 'q2r2_bringup'))
    software = software and package('rm65_teleop_adapter', 'launch/dual_quest_teleop.launch.py')
    hardware = (package('rm_driver', 'launch/rm_65_dual_driver.launch.py')
                and package('rm_control', 'launch/rm_65_dual_control.launch.py'))
    return software, hardware


def hand_sdk_available(environ):
    """Inspect the existing node's default path, never import or connect its SDK."""
    for value in environ.get('AMENT_PREFIX_PATH', '').split(os.pathsep):
        prefix = Path(value)
        if not (prefix / 'share/ament_index/resource_index/packages/rm65_teleop_adapter').is_file():
            continue
        try:
            node = prefix / 'lib/rm65_teleop_adapter/right_linkerhand_node'
            for statement in ast.parse(node.read_text(encoding='utf-8')).body:
                if (isinstance(statement, ast.Assign) and any(
                        isinstance(target, ast.Name) and target.id == 'DEFAULT_SDK_PATH'
                        for target in statement.targets)):
                    sdk = Path(ast.literal_eval(statement.value))
                    return (sdk / 'LinkerHand/core/rs485/realman_modbus.py').is_file()
        except (OSError, SyntaxError, ValueError, TypeError):
            return False
        return False
    return False


def session_members(session_id):
    members = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            # stat fields after comm: state, ppid, pgrp, session; ignore zombies.
            if int(fields[3]) == session_id and fields[0] != 'Z':
                members.append((int(entry.name), int(fields[2])))
        except (OSError, ValueError, IndexError):
            continue
    return members


class ProcessHandle:
    def __init__(self, process):
        self.process, self.pid = process, process.pid
        self._lines = deque(maxlen=1000)
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read, name=f'launch-log-{self.pid}', daemon=True)
        self._reader.start()

    def _read(self):
        with self.process.stdout as stream:
            for line in iter(lambda: stream.readline(4096), ''):
                with self._lock:
                    self._lines.append(line.rstrip())

    def poll(self):
        return self.process.poll()

    def alive(self):
        return self.poll() is None or bool(session_members(self.pid))

    def send_signal(self, sig):
        # Include descendants whose launch parent has already exited. They must
        # still belong to the session created by our own Popen call.
        groups = {group for _, group in session_members(self.pid)}
        if self.poll() is None:
            groups.add(self.pid)
        for group in groups:
            try:
                os.killpg(group, sig)
            except ProcessLookupError:
                pass

    def logs(self):
        with self._lock:
            return tuple(self._lines)


class SubprocessRunner:
    def __init__(self, environ):
        self.environ = dict(environ)

    def start(self, command):
        if sys.platform != 'linux':
            raise RuntimeError('Process management requires Ubuntu; Windows supports Demo only')
        process = subprocess.Popen(command, env=self.environ, start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                   errors='replace', bufsize=1)
        return ProcessHandle(process)
