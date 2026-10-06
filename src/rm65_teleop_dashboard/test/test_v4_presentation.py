"""Presentation-only changes must preserve the real runtime intent boundary."""
from dataclasses import replace
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtCore import QRect, QPoint
from PyQt5.QtGui import QImage
import pytest
from test_navigation import application
from rm65_teleop_dashboard.main_window import MainWindow
from rm65_teleop_dashboard.demo_data import demo_snapshot
from rm65_teleop_dashboard.runtime_service import RuntimeService, RuntimeSnapshot
from rm65_teleop_dashboard.process_manager import ProcessManager
from rm65_teleop_dashboard.view_config import PAGE_KEYS
from rm65_teleop_dashboard.widgets import Card, PrimaryPanel, MetricTile, SettingsGroup, RuntimeTimeline


def test_demo_preview_clicks_never_reach_process_manager(application, monkeypatch):
    starts = []
    monkeypatch.setattr(ProcessManager, 'start', lambda *args: starts.append(args))
    runtime = RuntimeService.demo()
    runtime.cycle()
    window = MainWindow()
    window.update_snapshot(demo_snapshot())
    window.update_runtime(runtime.snapshot())
    window.set_page('runtime-control')
    page = window.pages['runtime-control']
    page.start_requested.connect(runtime.request_start)
    page.stop_requested.connect(runtime.request_stop)
    requested, stopped = QSignalSpy(page.start_requested), QSignalSpy(page.stop_requested)
    window.show()
    application.processEvents()
    for mode in ('dry_run', 'hardware'):
        page.mode.select(mode)
        for button in (page.start_button, page.stop_button, page.rows['hand'][1]):
            assert button.property('demoPreview') is True
            assert not button.isEnabled()
            page.ensureWidgetVisible(button)
            QTest.mouseClick(button, Qt.LeftButton)
    runtime.cycle()
    assert len(requested) == len(stopped) == 0
    assert starts == []
    assert runtime.system.handle is runtime.hand.handle is None
    assert runtime._requests.empty()
    window.update_runtime(RuntimeSnapshot())
    assert page.start_button.property('demoPreview') is False
    window.close()
    runtime.close()


def test_new_presentation_components_render_existing_values(application):
    primary = PrimaryPanel('系统')
    metric = MetricTile('Quest', 'Hz', '左右控制器')
    metric.setText('72')
    settings = SettingsGroup('运行摘要')
    settings.settings.add('mode', '模式')
    settings.settings.set_value('mode', 'Dry Run')
    timeline = RuntimeTimeline((('env', 'ROS 2'), ('hand', 'LinkerHand')))
    timeline.steps['env'].set_state('READY', '就绪')
    assert primary.property('role') == 'primaryPanel'
    assert metric.value.text() == '72' and metric.unit.text() == 'Hz'
    assert settings.settings.fields['mode'].text() == 'Dry Run'
    assert timeline.steps['env'].state_label.text() == '就绪'
    assert timeline.steps['env'].first and timeline.steps['hand'].last
    for widget in (primary, metric, settings, timeline):
        widget.show()
        application.processEvents()
        assert not widget.grab().isNull()
        widget.close()


def test_runtime_settings_owns_actions_and_primary_owns_flow(application):
    window = MainWindow()
    page = window.pages['runtime-control']
    assert isinstance(page.primary, PrimaryPanel)
    assert page.primary.isAncestorOf(page.flow)
    assert page.settings_panel.isAncestorOf(page.start_button)
    assert page.settings_panel.isAncestorOf(page.mode)
    assert page.settings_panel.isAncestorOf(page.profile)
    assert page.start_button.property('role') == 'primaryAction'
    assert page.start_button.height() == 44
    assert len(page.flow.nodes) == 6
    assert page.rows['driver'][1].text() == '由系统管理'
    window.close()


@pytest.mark.parametrize('size', ((1920, 1080), (1366, 768)))
@pytest.mark.parametrize('key', PAGE_KEYS)
def test_v4_screenshots_have_disjoint_surfaces_and_readable_geometry(application, size, key, tmp_path):
    window = MainWindow()
    window.resize(*size)
    runtime = RuntimeService.demo()
    runtime.cycle()
    window.update_snapshot(demo_snapshot(1))
    window.update_runtime(runtime.snapshot())
    window.set_page(key)
    window.show()
    application.processEvents()
    page = window.pages[key]
    assert window.sidebar.width() == (224 if size[0] >= 1600 else 196)
    assert page.content.width() <= 1480
    assert page.widget().width() <= page.viewport().width()
    cards = [card for card in page.findChildren(Card) if card.isVisible()]
    rects = [QRect(card.mapTo(page.content, QPoint()), card.size()) for card in cards]
    assert all(not first.intersects(second) for i, first in enumerate(rects) for second in rects[i + 1:])
    if key == 'runtime-control':
        assert page.start_button.isVisible()
        assert page.start_button.font().pixelSize() >= 14
    target = tmp_path / (key + '.png')
    assert window.grab().save(str(target))
    rendered = QImage(str(target))
    assert (rendered.width(), rendered.height()) == size
    window.close()
    runtime.close()
