"""Exercise the software smoke barrier without importing or starting ROS."""
from dataclasses import replace
import importlib.util
from pathlib import Path

from rm65_teleop_dashboard.demo_data import demo_snapshot
from rm65_teleop_dashboard.runtime_observer import GraphEvidence, NODES


spec = importlib.util.spec_from_file_location('runtime_probe',
    Path(__file__).resolve().parents[3] / 'tools' / 'dashboard_runtime_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_adapters_arriving_before_tcp_and_nodes_do_not_finish_smoke():
    data = demo_snapshot()
    data = replace(data,
        left=replace(data.left, adapter=replace(data.left.adapter, dry_run=True)),
        right=replace(data.right, adapter=replace(data.right.adapter, dry_run=True)))
    nodes = NODES['quest'] + NODES['adapter']
    samples = iter((GraphEvidence(nodes=NODES['adapter']),
                    GraphEvidence(nodes=nodes),
                    GraphEvidence(nodes=nodes, tcp_listening=True)))
    observations = []

    def started():
        graph = next(samples)
        observations.append(graph)
        return probe.software_started(data, graph)

    probe.wait_until(started, timeout=2)
    assert len(observations) == 3


def test_complete_graph_does_not_hide_invalid_stale_or_hardware_feedback():
    from rm65_teleop_dashboard.models import StreamHealth
    data = demo_snapshot()
    data = replace(data,
        left=replace(data.left, adapter=replace(data.left.adapter, dry_run=True)),
        right=replace(data.right, adapter=replace(data.right.adapter, dry_run=True)))
    graph = GraphEvidence(nodes=NODES['quest'] + NODES['adapter'], tcp_listening=True)
    assert probe.software_started(data, graph)
    for arm in (replace(data.left, status_health=StreamHealth()),
                replace(data.left, adapter=replace(data.left.adapter, parse_error='invalid')),
                replace(data.left, adapter=replace(data.left.adapter, dry_run=False))):
        assert not probe.software_started(replace(data, left=arm), graph)
    assert not probe.software_started(data, replace(graph, graph_ok=False))
    assert not probe.software_started(data, replace(graph, nodes=graph.nodes[:-1]))
    assert not probe.software_started(data, replace(graph, nodes=graph.nodes + (graph.nodes[0],)))
