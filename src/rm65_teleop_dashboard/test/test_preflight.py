from dataclasses import replace
import pytest
from rm65_teleop_dashboard.preflight import PreflightFacts, Confirmation, evaluate_preflight


def facts():
    return PreflightFacts(domain='42', environment_ok=True, hardware_packages=True,
                          graph_ok=True, process_scan_ok=True, tcp_port_free=True)


@pytest.mark.parametrize('field,value', [('domain', 'bad'), ('domain', '233'),
    ('environment_ok', False), ('hardware_packages', False), ('graph_ok', False),
    ('process_scan_ok', False), ('tcp_port_free', False), ('duplicate_driver', True),
    ('duplicate_control', True), ('stack_running', True), ('hand_running', True)])
def test_hardware_blockers(field, value):
    result = evaluate_preflight(replace(facts(), **{field: value}), 'hardware')
    assert not result.can_start(Confirmation(True, True, True))


def test_all_manual_confirmations_required_and_quest_is_warning_before_tcp():
    result = evaluate_preflight(facts(), 'hardware')
    assert result.allowed
    assert not result.can_start(Confirmation())
    assert not result.can_start(Confirmation(True, True, False))
    assert result.can_start(Confirmation(True, True, True))
    assert next(c for c in result.checks if c.key == 'quest').level == 'warning'


def test_dry_run_does_not_require_hardware_packages_or_confirmation():
    result = evaluate_preflight(replace(facts(), hardware_packages=False), 'dry_run')
    assert result.can_start(Confirmation())
    # Avoid synthetic command chains sharing a domain with an active real stack.
    assert not evaluate_preflight(replace(facts(), duplicate_driver=True), 'dry_run').allowed


def test_hardware_hand_sdk_missing_is_blocking_even_with_manual_consent():
    result = evaluate_preflight(facts(), 'hardware', 'hand')
    assert not result.can_start(Confirmation(True, True, True, True))
