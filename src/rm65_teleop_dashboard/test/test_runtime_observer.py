from dataclasses import replace
from rm65_teleop_dashboard.demo_data import demo_snapshot
from rm65_teleop_dashboard.models import SystemSnapshot, StreamHealth
from rm65_teleop_dashboard.runtime_observer import GraphEvidence, component_states, component_dependencies


def test_nodes_and_target_alone_do_not_prove_input_or_robot_ready():
    graph = GraphEvidence(nodes=('/UnityEndpoint', '/quest_left_target_bridge',
        '/quest_right_target_bridge', '/left/rm_driver', '/right/rm_driver'), tcp_listening=True)
    states = {c.key: c for c in component_states(graph, SystemSnapshot(), 'hardware')}
    assert states['quest'].state != 'READY'
    assert states['driver'].state != 'READY'
    assert states['driver'].ownership == 'External'


def test_real_feedback_unique_nodes_and_status_required():
    graph = GraphEvidence(nodes=('/UnityEndpoint', '/quest_left_target_bridge',
        '/quest_right_target_bridge', '/left/rm_driver', '/right/rm_driver',
        '/left/rm_control', '/right/rm_control', '/left_rm65_teleop_adapter',
        '/rm65_teleop_adapter'), tcp_listening=True)
    data = demo_snapshot()
    states = {c.key: c for c in component_states(graph, data, 'hardware', owned=True)}
    assert all(states[k].state == 'READY' for k in ('driver', 'control', 'quest', 'adapter'))
    assert states['hand'].state == 'STOPPED'
    duplicate = replace(graph, nodes=graph.nodes + ('/right/rm_driver',))
    assert next(c for c in component_states(duplicate, data, 'hardware') if c.key == 'driver').state == 'FAILED'
    stale = replace(data, left=replace(data.left, status_health=StreamHealth()))
    assert next(c for c in component_states(graph, stale, 'hardware') if c.key == 'adapter').state != 'READY'


def test_dry_run_dependency_has_no_driver_or_control():
    assert component_dependencies('dry_run')['adapter'] == ('quest',)
    assert set(component_dependencies('hardware')['adapter']) == {'quest', 'driver', 'control'}
    states = {c.key: c for c in component_states(GraphEvidence(), SystemSnapshot(), 'dry_run')}
    assert states['driver'].state == states['control'].state == 'DISABLED'


def test_hand_fresh_fault_is_not_ready_and_mode_is_independent():
    data = demo_snapshot()
    graph = GraphEvidence(nodes=('/right_linkerhand',))
    for state in ('COMM_ERROR', 'HAND_FAULT', 'INPUT_STALE'):
        hand = replace(data.linkerhand, state=state)
        component = component_states(graph, replace(data, linkerhand=hand), 'dry_run',
                                     hand_mode='hardware')[-1]
        assert component.state != 'READY'
    mismatch = replace(data.linkerhand, state='READY', dry_run=False)
    assert component_states(graph, replace(data, linkerhand=mismatch), 'dry_run',
                            hand_mode='dry_run')[-1].state != 'READY'


def test_actual_hand_dry_run_status_and_hardware_feedback_gates():
    data = demo_snapshot()
    graph = GraphEvidence(nodes=('/right_linkerhand',))
    hand = replace(data.linkerhand, state='DRY_RUN', dry_run=True, communication_ok=False,
                   actual=None, fault_codes=None)
    assert component_states(graph, replace(data, linkerhand=hand), 'hardware',
                            hand_mode='dry_run')[-1].state == 'READY'
    assert component_states(graph, data, 'dry_run', hand_mode='hardware')[-1].state == 'READY'
    hand = replace(data.linkerhand, fault_codes=(1, 0, 0, 0, 0, 0, 0))
    assert component_states(graph, replace(data, linkerhand=hand), 'dry_run',
                            hand_mode='hardware')[-1].state != 'READY'
    hand = replace(data.linkerhand, state='CONNECT_ONLY', connect_only=True, input_fresh=False)
    assert component_states(graph, replace(data, linkerhand=hand), 'dry_run')[-1].state == 'READY'


def test_dry_run_never_claims_external_driver_ownership():
    graph = GraphEvidence(nodes=('/left/rm_driver', '/right/rm_driver'))
    states = component_states(graph, demo_snapshot(), 'dry_run', owned=True)
    assert next(c for c in states if c.key == 'driver').ownership == 'External'


def test_legacy_hand_status_with_unknown_mode_is_not_ready():
    data = demo_snapshot()
    graph = GraphEvidence(nodes=('/right_linkerhand',))
    hand = replace(data.linkerhand, dry_run=None, communication_ok=None, fault_codes=None)
    assert component_states(graph, replace(data, linkerhand=hand), 'hardware')[-1].state != 'READY'
