"""Flow is a presentation of existing telemetry, never a readiness authority."""
from dataclasses import replace
import pytest
from test_navigation import application
from rm65_teleop_dashboard.demo_data import demo_snapshot
from rm65_teleop_dashboard.models import StreamHealth, summarize_system
from rm65_teleop_dashboard.flow_widget import FlowNode, TeleopFlowWidget, link_color, node_color
from rm65_teleop_dashboard.runtime_service import ProcessInfo, RuntimeSnapshot
from rm65_teleop_dashboard.runtime_observer import ComponentState
from rm65_teleop_dashboard.preflight import PreflightFacts


def test_demo_flow_preserves_two_arm_states(application):
    flow = TeleopFlowWidget()
    source = demo_snapshot()
    flow.set_snapshot(source)
    assert flow.nodes['quest_left'].state == 'ONLINE'
    assert flow.nodes['quest_right'].state == 'ONLINE'
    assert flow.nodes['left'].state == 'ACTIVE'
    assert flow.nodes['right'].state == 'ARMED'
    assert flow.nodes['teleop'].state == 'READY'
    assert flow.nodes['hand'].detail == 'READY · OPEN'
    assert source.left.adapter.state == 'ACTIVE'
    flow.resize(1000, 110)
    assert not flow.grab().isNull()


@pytest.mark.parametrize('side', ('left', 'right'))
def test_fresh_adapter_fault_is_visible_on_its_branch_and_teleop(application, side):
    source = demo_snapshot()
    arm = getattr(source, side)
    flow = TeleopFlowWidget()
    flow.set_snapshot(replace(source, **{side: replace(arm, adapter=replace(arm.adapter, state='FAULT'))}))
    assert flow.nodes[side].state == flow.nodes['teleop'].state == 'FAULT'
    assert link_color(flow.nodes['teleop'], flow.nodes[side]) == '#FF3B30'


def test_old_fault_cannot_reappear_as_live_and_bad_status_is_visible(application):
    source = demo_snapshot()
    flow = TeleopFlowWidget()
    old = replace(source.right, status_health=StreamHealth(), adapter=replace(source.right.adapter, state='FAULT'))
    flow.set_snapshot(replace(source, right=old))
    assert flow.nodes['right'].state != 'FAULT'
    assert flow.nodes['teleop'].state == 'STALE'
    flow.set_snapshot(replace(source, right=replace(source.right,
        adapter=replace(source.right.adapter, parse_error='bad JSON'))))
    assert flow.nodes['right'].state == flow.nodes['teleop'].state == 'DATA_ERROR'


def test_quest_inputs_offline_does_not_hide_other_controller(application):
    source = demo_snapshot()
    flow = TeleopFlowWidget()
    flow.set_snapshot(replace(source, left_controller=replace(source.left_controller, inputs_health=StreamHealth())))
    assert flow.nodes['quest_left'].state == 'STALE'
    assert flow.nodes['quest_right'].state == 'ONLINE'
    assert link_color(flow.nodes['quest_left'], flow.nodes['ros'], active=True) == '#FF9F0A'


def test_robot_requires_feedback_and_optional_hand_does_not_change_system(application):
    source = demo_snapshot()
    flow = TeleopFlowWidget()
    source = replace(source, linkerhand=replace(source.linkerhand, health=StreamHealth()))
    before = summarize_system(source)
    flow.set_snapshot(source)
    assert flow.nodes['hand'].optional
    assert node_color(flow.nodes['hand']) == '#8E8E93'
    assert summarize_system(source) == before == 'SYSTEM READY'
    flow.set_snapshot(replace(source, left=replace(source.left, robot_health=StreamHealth())))
    assert flow.nodes['left'].state == 'STALE'
    assert 'left' not in flow.active_sides


def test_ros_graph_failure_is_not_ready(application):
    flow = TeleopFlowWidget()
    flow.set_snapshot(replace(demo_snapshot(), monitor_error='graph unavailable'))
    assert flow.nodes['ros'].state == 'FAULT'


@pytest.mark.parametrize('stream', ('quest', 'target'))
def test_active_lines_require_current_input_and_target_evidence(application, stream):
    source = demo_snapshot()
    stale = StreamHealth('STALE', 800, 0)
    source = (replace(source, left_controller=replace(source.left_controller, inputs_health=stale))
              if stream == 'quest' else replace(source, left=replace(source.left, target_health=stale)))
    flow = TeleopFlowWidget()
    flow.set_snapshot(source)
    assert flow.nodes['left'].state == 'ACTIVE'  # Keep the reported adapter state visible.
    assert 'left' not in flow.active_sides


@pytest.mark.parametrize('external', (False, True))
def test_future_state_is_neutral_not_an_invented_fault_or_ready_path(external):
    unknown = FlowNode('left', 'Left RM65', 'FUTURE_STATE', 'FUTURE_STATE', external=external)
    ready = FlowNode('teleop', 'Teleop', 'READY', 'READY')
    assert node_color(unknown) == '#8E8E93'
    assert link_color(ready, unknown, active=True) == '#D1D1D6'


def test_optional_hand_never_seen_differs_from_feedback_lost(application):
    source = demo_snapshot()
    flow = TeleopFlowWidget()
    flow.set_snapshot(replace(source, linkerhand=replace(source.linkerhand, health=StreamHealth())))
    assert flow.nodes['hand'].detail == '可选 · Offline'
    flow.set_snapshot(replace(source, linkerhand=replace(source.linkerhand,
        health=StreamHealth('OFFLINE', 8000, 0))))
    assert 'LOST' in flow.nodes['hand'].detail


@pytest.mark.parametrize('state,color', (('STOPPED', '#8E8E93'), ('STARTING', '#007AFF'),
    ('READY', '#34C759'), ('WAITING', '#FF9F0A'), ('FAILED', '#FF3B30')))
def test_runtime_flow_uses_component_evidence(application, state, color):
    flow = TeleopFlowWidget('runtime')
    flow.set_runtime(RuntimeSnapshot(system=ProcessInfo(state='RUNNING', pid=123),
        components=(ComponentState('adapter', state, 'Managed'),)))
    assert flow.nodes['adapter'].state == state
    assert node_color(flow.nodes['adapter']) == color
    assert flow.nodes['driver'].state == 'STOPPED'
    assert flow.nodes['hand'].optional
    flow.resize(1000, 66)
    assert not flow.grab().isNull()


def test_runtime_external_ownership_does_not_mask_failure(application):
    flow = TeleopFlowWidget('runtime')
    for state, color in (('READY', '#829AB5'), ('FAILED', '#FF3B30')):
        flow.set_runtime(RuntimeSnapshot(components=(ComponentState('driver', state, 'External'),)))
        assert flow.nodes['driver'].external
        assert '外部管理' in flow.nodes['driver'].detail
        assert node_color(flow.nodes['driver']) == color


def test_demo_runtime_does_not_fabricate_ready_or_processes(application):
    flow = TeleopFlowWidget('runtime')
    flow.set_runtime(RuntimeSnapshot(demo=True))
    assert all(node.state == 'STOPPED' for node in flow.nodes.values())
    assert flow.nodes['hand'].detail == '可选 · 未启动'


@pytest.mark.parametrize('size', ((1280, 720), (1366, 768), (1920, 1080)))
@pytest.mark.parametrize('page_key', ('overview', 'runtime-control'))
def test_pages_receive_flow_snapshots_without_overlap(application, size, page_key, tmp_path):
    from rm65_teleop_dashboard.main_window import MainWindow
    window = MainWindow()
    window.resize(*size)
    window.update_snapshot(demo_snapshot())
    window.update_runtime(RuntimeSnapshot(demo=True))
    window.set_page(page_key)
    window.show()
    application.processEvents()
    flow = window.pages[page_key].flow
    assert len(flow.nodes) == (7 if page_key == 'overview' else 6)
    if page_key == 'overview':
        assert flow.nodes['left'].state == 'ACTIVE'
        assert window.pages[page_key].verticalScrollBar().maximum() == 0
    rects = list(flow.node_rects().values())
    assert all(not a.intersects(b) for i, a in enumerate(rects) for b in rects[i + 1:])
    assert window.grab().save(str(tmp_path / (page_key + '.png')))
    window.close()
