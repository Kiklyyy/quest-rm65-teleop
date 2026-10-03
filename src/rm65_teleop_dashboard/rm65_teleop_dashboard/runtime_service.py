"""Background process supervisor; immutable copies cross into the Qt thread."""
from dataclasses import dataclass
import queue
import threading
import time
from typing import Optional, Tuple
from .models import EventRecord, SystemSnapshot
from .preflight import Confirmation, PreflightFacts, evaluate_preflight
from .process_environment import SubprocessRunner, environment_packages, hand_sdk_available
from .process_manager import LaunchRequest, ProcessManager
from .runtime_observer import (ComponentState, GraphEvidence, NODES, component_states,
                               component_dependencies, quest_fresh)


@dataclass(frozen=True)
class ProcessInfo:
    state: str = 'STOPPED'
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    mode: str = 'dry_run'
    profile: str = 'safe'
    error: str = ''


@dataclass(frozen=True)
class RuntimeSnapshot:
    enabled: bool = False
    demo: bool = False
    system: ProcessInfo = ProcessInfo()
    hand: ProcessInfo = ProcessInfo()
    facts: PreflightFacts = PreflightFacts()
    components: Tuple[ComponentState, ...] = ()
    events: Tuple[EventRecord, ...] = ()
    system_logs: Tuple[str, ...] = ()
    hand_logs: Tuple[str, ...] = ()
    ready: bool = False


def process_info(manager):
    return ProcessInfo(manager.state, manager.handle.pid if manager.handle else None,
                       manager.exit_code, manager.request.mode, manager.request.profile, manager.error)


class RuntimeService:
    def __init__(self, graph_provider, snapshot_provider, environ, runner=None,
                 packages=None, enabled=True, demo=False):
        self.graph_provider, self.snapshot_provider = graph_provider, snapshot_provider
        self.environ = dict(environ)
        self.packages = packages if packages is not None else environment_packages(environ)
        self.enabled, self.is_demo = enabled, demo
        runner = runner or SubprocessRunner(environ)
        self.system = ProcessManager(runner)
        self.hand = ProcessManager(runner, source='linkerhand_process')
        self._requests = queue.Queue(maxsize=20)
        self._stop_requests = set()
        self._stop_lock = threading.Lock()
        self._lock = threading.Lock()
        self._snapshot = RuntimeSnapshot()
        self._closing = threading.Event()
        self._thread = None

    @classmethod
    def demo(cls):
        # Demo never fabricates managed PIDs or permits process startup.
        return cls(GraphEvidence, SystemSnapshot, {}, enabled=False, demo=True, packages=(False, False))

    def request_start(self, request, confirmation=Confirmation()):
        if self.enabled and not self._closing.is_set():
            self._enqueue(('start', request, confirmation))

    def request_stop(self, component='all'):
        with self._stop_lock:
            self._stop_requests.add(component)

    def _enqueue(self, value):
        try:
            self._requests.put_nowait(value)
        except queue.Full:
            pass  # Button bursts cannot accumulate unbounded work.

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name='dashboard-processes', daemon=False)
        self._thread.start()

    def _run(self):
        while True:
            if self._closing.is_set():
                # Shutdown must not depend on graph reads; the ROS context may
                # already be unavailable. Only owned handles are needed here.
                self.hand.stop()
                self.system.stop()
                self.hand.tick()
                self.system.tick()
                if self.hand.handle is None and self.system.handle is None:
                    break
                time.sleep(.1)
                continue
            try:
                self.cycle()
            except Exception as exc:
                self.system.error = str(exc)
                self.system.event('RUNTIME_OBSERVER_ERROR', str(exc), 'ERROR')
                # Failed observation must revoke any previous ready/preflight result.
                with self._lock:
                    self._snapshot = RuntimeSnapshot(enabled=self.enabled,
                        system=process_info(self.system), hand=process_info(self.hand),
                        facts=PreflightFacts(detail=str(exc)), events=tuple(self.system.events))
                self.system.tick()
                self.hand.tick()
            self._closing.wait(.5)

    def cycle(self):
        self.system.tick()
        self.hand.tick()
        # Stop is independent of graph availability and cannot be dropped by a
        # full startup queue. It also cancels pending starts instead of restarting.
        with self._stop_lock:
            stops = self._stop_requests.copy()
            self._stop_requests.clear()
        if stops:
            if stops & {'all', 'hand'}:
                self.hand.stop()
            if stops & {'all', 'system'}:
                self.system.stop()
            while not self._requests.empty():
                try:
                    self._requests.get_nowait()
                except queue.Empty:
                    break
        graph = self.graph_provider()
        data = self.snapshot_provider()
        facts = self._facts(graph, data)
        # At most one startup per observation. Every subsequent queued click
        # receives fresh graph/process evidence on the next worker iteration.
        try:
            action, value, confirmation = self._requests.get_nowait()
        except queue.Empty:
            action = None
        if action == 'start' and not self._closing.is_set() and self.enabled:
            manager = self.hand if value.component == 'hand' else self.system
            try:
                manager.start(value, evaluate_preflight(facts, value.mode, value.component), confirmation)
            except (ValueError, RuntimeError) as exc:
                manager.event('START_BLOCKED', str(exc), 'WARN')
                manager.error = str(exc)
        components = component_states(graph, data, self.system.request.mode,
            self.system.handle is not None, self.hand.handle is not None,
            self.hand.request.mode if self.hand.handle else None)
        required = ('adapter', *component_dependencies(self.system.request.mode)['adapter'])
        states = {c.key: c.state for c in components}
        ready = all(states[k] == 'READY' for k in required)
        ready &= all(a.adapter.state in ('DISABLED', 'ARMED', 'ACTIVE', 'HOMING', 'REARM_REQUIRED')
                     and a.adapter.dry_run == (self.system.request.mode == 'dry_run')
                     for a in (data.left, data.right))
        self.system.set_ready(ready)
        self.hand.set_ready(states['hand'] == 'READY')
        events = tuple(sorted((*self.system.events, *self.hand.events), key=lambda e: e.time_s)[-500:])
        snapshot = RuntimeSnapshot(self.enabled, self.is_demo, process_info(self.system), process_info(self.hand),
            facts, components, events, self.system.logs(), self.hand.logs(), self.system.ready)
        with self._lock:
            self._snapshot = snapshot

    def _facts(self, graph, data):
        detected = lambda key: any(n in graph.nodes for n in NODES[key])
        return PreflightFacts(domain=self.environ.get('ROS_DOMAIN_ID', '0'),
            environment_ok=self.packages[0] and self.enabled, hardware_packages=self.packages[1],
            graph_ok=graph.graph_ok, process_scan_ok=graph.process_scan_ok,
            tcp_port_free=graph.tcp_port_free,
            duplicate_driver=detected('driver') or 'rm_driver' in graph.processes,
            duplicate_control=detected('control') or 'rm_control' in graph.processes,
            stack_running=self.system.handle is not None or detected('adapter') or 'rm65_teleop_adapter_node' in graph.processes,
            hand_running=self.hand.handle is not None or detected('hand') or 'right_linkerhand_node' in graph.processes,
            hand_sdk_ok=hand_sdk_available(self.environ) if self.enabled else False,
            quest_available=quest_fresh(data), detail='Demo：仅展示，不启动进程' if self.is_demo else graph.error)

    def snapshot(self):
        with self._lock:
            return self._snapshot

    def close(self):
        self._closing.set()
        if self._thread is not None:
            self._thread.join(timeout=22)
            if self._thread.is_alive():
                raise RuntimeError('Owned process cleanup still pending; supervisor remains active')
        else:
            self.hand.stop()
            self.system.stop()
            deadline = time.monotonic() + 22
            while self.hand.handle is not None or self.system.handle is not None:
                self.hand.tick()
                self.system.tick()
                if time.monotonic() > deadline:
                    raise RuntimeError('Owned process cleanup timeout')
                if self.hand.handle is not None or self.system.handle is not None:
                    time.sleep(.05)
