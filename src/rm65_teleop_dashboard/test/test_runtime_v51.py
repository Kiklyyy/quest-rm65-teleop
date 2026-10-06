"""One selected mode and one start action, preserving the runtime boundary."""
from PyQt5.QtWidgets import QDialog, QPushButton
from PyQt5.QtCore import QRect, QPoint
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtTest import QSignalSpy
import pytest
from test_navigation import application
from rm65_teleop_dashboard.main_window import MainWindow
from rm65_teleop_dashboard.demo_data import demo_snapshot
from rm65_teleop_dashboard.runtime_service import ProcessInfo, RuntimeSnapshot
from rm65_teleop_dashboard.pages.runtime_page import RuntimePage
from rm65_teleop_dashboard.preflight import PreflightFacts
from rm65_teleop_dashboard.process_manager import LaunchRequest
from rm65_teleop_dashboard.runtime_dialogs import HardwareConfirmation


def available_runtime(**kwargs):
    return RuntimeSnapshot(enabled=True, facts=PreflightFacts(environment_ok=True,
        hardware_packages=True, graph_ok=True, process_scan_ok=True, tcp_port_free=True), **kwargs)


def test_dry_run_is_a_mode_not_a_second_action(application):
    page = RuntimePage()
    assert not hasattr(page, 'dry_button')
    assert all(button.text() != 'Dry Run' for button in page.findChildren(QPushButton))
    assert page.mode.current == 'dry_run'
    assert list(page.profile.itemText(i) for i in range(page.profile.count())) == ['Safe', 'Normal']
    page.close()


@pytest.mark.parametrize('mode', ('dry_run', 'hardware'))
@pytest.mark.parametrize('profile', ('Safe', 'Normal'))
def test_selected_mode_and_profile_use_the_existing_start_path(application, monkeypatch, mode, profile):
    dialogs = []

    def confirm(dialog):
        dialogs.append(dialog.result)
        assert dialog.result.mode == 'hardware'
        assert not dialog.start_button.isEnabled()
        for checkbox in dialog.checkboxes:
            checkbox.setChecked(True)
        assert dialog.start_button.isEnabled()
        return QDialog.Accepted

    monkeypatch.setattr(HardwareConfirmation, 'exec_', confirm)
    page = RuntimePage()
    page.update_runtime(available_runtime())
    page.mode.select(mode)
    page.profile.setCurrentText(profile)
    requested = QSignalSpy(page.start_requested)
    assert page.start_button.isEnabled()
    page.start_button.click()
    assert len(requested) == 1
    assert requested[0][0] == LaunchRequest(mode, profile.lower(), 'system')
    assert requested[0][1].complete == (mode == 'hardware')
    assert len(dialogs) == (1 if mode == 'hardware' else 0)
    page.close()


@pytest.mark.parametrize('outcome', ('rejected', 'incomplete'))
def test_hardware_confirmation_cannot_be_bypassed(application, monkeypatch, outcome):
    def confirm(dialog):
        assert not dialog.start_button.isEnabled()
        dialog.checkboxes[0].setChecked(True)
        assert not dialog.start_button.isEnabled()
        return QDialog.Rejected if outcome == 'rejected' else QDialog.Accepted

    monkeypatch.setattr(HardwareConfirmation, 'exec_', confirm)
    page = RuntimePage()
    page.update_runtime(available_runtime())
    page.mode.select('hardware')
    requested = QSignalSpy(page.start_requested)
    page.start_button.click()
    assert len(requested) == 0
    page.close()


def test_stop_still_requests_all_owned_processes(application):
    page = RuntimePage()
    stopped = QSignalSpy(page.stop_requested)
    page.update_runtime(available_runtime())
    assert not page.stop_button.isEnabled()
    page.update_runtime(available_runtime(system=ProcessInfo(state='RUNNING', pid=123)))
    assert page.stop_button.isEnabled()
    page.stop_button.click()
    assert list(stopped) == [['all']]
    page.close()


@pytest.mark.parametrize('size', ((1920, 1080), (1366, 768), (1280, 720)))
def test_status_and_settings_are_separate_equal_height_panels(application, size, tmp_path):
    window = MainWindow()
    window.resize(*size)
    window.set_page('runtime-control')
    window.update_snapshot(demo_snapshot())
    window.update_runtime(RuntimeSnapshot(demo=True))
    window.show()
    application.processEvents()
    page = window.pages['runtime-control']
    assert page.primary.isAncestorOf(page.flow)
    assert not page.primary.isAncestorOf(page.start_button)
    settings = page.settings_panel
    for control in (page.mode, page.profile, page.start_button, page.stop_button):
        assert settings.isAncestorOf(control)
        rect = QRect(control.mapTo(settings, QPoint()), control.size())
        assert settings.rect().contains(rect)
    left = QRect(page.primary.mapTo(page.content, QPoint()), page.primary.size())
    right = QRect(settings.mapTo(page.content, QPoint()), settings.size())
    assert left.right() < right.left()
    assert left.top() == right.top() and left.height() == right.height()
    assert page.mode.y() < page.profile.y() < page.start_button.y() < page.stop_button.y()
    assert page.profile.width() == page.start_button.width()
    assert page.process_status.text() == '未运行'
    assert page.flow_caption.text() == 'Demo 模式不会启动真实进程'
    font = QFont(page.flow.font())
    font.setPixelSize(13)
    font.setWeight(QFont.Medium)
    metrics = QFontMetrics(font)
    for key, rect in page.flow.node_rects().items():
        assert metrics.horizontalAdvance(page.flow.nodes[key].title) <= rect.width() - 20
    assert page.widget().width() <= page.viewport().width()
    assert window.grab().save(str(tmp_path / 'runtime-control.png'))
    window.close()
