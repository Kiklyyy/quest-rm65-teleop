from dataclasses import replace
from test_navigation import application
from rm65_teleop_dashboard.main_window import MainWindow
from rm65_teleop_dashboard.models import SystemSnapshot
from rm65_teleop_dashboard.preflight import PreflightFacts, evaluate_preflight
from rm65_teleop_dashboard.runtime_service import RuntimeSnapshot
from rm65_teleop_dashboard.pages.runtime_page import HardwareConfirmation


def test_runtime_navigation_and_demo_cannot_start(application):
    window = MainWindow()
    window.set_page('runtime-control')
    window.update_runtime(RuntimeSnapshot(demo=True))
    assert window.current_page == 'runtime-control'
    page = window.pages['runtime-control']
    assert not page.start_button.isEnabled()
    assert not page.dry_button.isEnabled()
    assert not page.stop_button.isEnabled()
    window.close()


def test_hardware_sheet_requires_all_manual_items_and_preflight(application):
    facts = PreflightFacts(environment_ok=True, hardware_packages=True, graph_ok=True,
                           process_scan_ok=True, tcp_port_free=True)
    dialog = HardwareConfirmation(evaluate_preflight(facts, 'hardware'))
    assert not dialog.start_button.isEnabled()
    for checkbox in dialog.checkboxes:
        checkbox.setChecked(True)
    assert dialog.start_button.isEnabled()
    assert dialog.confirmation().complete
    dialog.update_preflight(evaluate_preflight(replace(facts, tcp_port_free=False), 'hardware'))
    assert not dialog.start_button.isEnabled()
    dialog.close()


def test_dry_run_button_emits_request_not_ros_command(application):
    window = MainWindow()
    window.update_snapshot(SystemSnapshot())
    window.update_runtime(RuntimeSnapshot(enabled=True, facts=PreflightFacts(
        environment_ok=True, graph_ok=True, process_scan_ok=True, tcp_port_free=True)))
    page = window.pages['runtime-control']
    requests = []
    page.start_requested.connect(lambda req, confirmation: requests.append(req))
    page.dry_button.click()
    assert len(requests) == 1 and requests[0].mode == 'dry_run'
    window.close()
