"""Read-only navigation behavior, without a ROS runtime."""
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
qt_package = pytest.importorskip('PyQt5')
if os.name == 'nt':
    os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', str(
        Path(qt_package.__file__).parent / 'Qt5' / 'plugins' / 'platforms'))
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from dataclasses import replace
from rm65_teleop_dashboard.demo_data import demo_snapshot
from rm65_teleop_dashboard.models import EventRecord, StreamHealth, SystemSnapshot
from rm65_teleop_dashboard.main_window import MainWindow
from rm65_teleop_dashboard.view_config import PAGE_KEYS


@pytest.fixture(scope='module')
def application():
    app = QApplication.instance() or QApplication([])
    if os.name == 'nt' and not QFontDatabase().families():
        for name in ('msyh.ttc', 'segoeui.ttf', 'consola.ttf'):
            path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
    return app


def test_navigation_selects_independent_pages(application):
    window = MainWindow()
    assert window.current_page == 'overview'
    for key in ('overview', 'arms', 'controllers', 'safety', 'linkerhand', 'events'):
        window.set_page(key)
        assert window.current_page == key
        assert window.stack.currentWidget() is window.pages[key]
    with pytest.raises(ValueError):
        window.set_page('not-a-page')
    assert window.current_page == 'events'
    window.close()


def test_sidebar_click_switches_the_visible_page(application):
    window = MainWindow()
    window.show()
    application.processEvents()
    for index, key in enumerate(PAGE_KEYS):
        item = window.navigation.item(index)
        point = window.navigation.visualItemRect(item).center()
        QTest.mouseClick(window.navigation.viewport(), Qt.LeftButton, pos=point)
        assert window.current_page == key
        assert window.pages[key].isVisible()
    window.close()


@pytest.mark.parametrize('key', PAGE_KEYS)
def test_each_page_accepts_offline_and_demo_at_minimum_size(application, key):
    window = MainWindow()
    window.resize(1280, 720)
    window.set_page(key)
    window.update_snapshot(SystemSnapshot())
    window.show()
    application.processEvents()
    window.update_snapshot(demo_snapshot(2.0))
    application.processEvents()
    page = window.pages[key]
    assert (window.width(), window.height()) == (1280, 720)
    assert page.widget().width() <= page.viewport().width()
    assert page.content.width() <= page.viewport().width()
    assert not window.grab().isNull()
    if key == 'overview':
        assert page.verticalScrollBar().maximum() == 0
    window.close()


def test_hidden_pages_receive_latest_values_and_stale_cannot_resurrect_ready(application):
    window = MainWindow()
    snapshot = demo_snapshot()
    fault = replace(snapshot, right=replace(snapshot.right,
        adapter=replace(snapshot.right.adapter, state='FAULT', reason='feedback fault ' * 30)),
        linkerhand=replace(snapshot.linkerhand, hand_toggle_state='CLOSED'),
        events=(EventRecord(1700000000, 'ERROR', 'right_arm', 'feedback fault'),))
    window.update_snapshot(snapshot)
    window.update_snapshot(fault)
    assert window.current_page == 'overview'
    window.set_page('arms')
    window.pages['arms'].selector.select('right')
    assert window.pages['arms'].arms['right'].state_label.text() == 'FAULT'
    window.set_page('linkerhand')
    assert window.pages['linkerhand'].summary_values['state'].text() == 'Closed'
    window.set_page('events')
    assert window.pages['events'].table.item(0, 3).text() == 'feedback fault'
    stale = StreamHealth('STALE', 1200, 0)
    window.update_snapshot(replace(snapshot,
        left=replace(snapshot.left, status_health=stale),
        right=replace(snapshot.right, status_health=stale),
        linkerhand=replace(snapshot.linkerhand, health=stale)))
    for side in ('left', 'right'):
        panel = window.pages['arms'].arms[side]
        assert panel.state_label.text() == 'STALE'
        assert panel.cart.text() == panel.home.text() == 'STALE'
        assert window.pages['safety'].sections[side].settings.fields['command_path_ready'].text() == 'STALE'
    assert window.pages['linkerhand'].channel_rows[0][1].text() == '—'
    window.close()


def test_arm_selection_and_details_are_display_only(application):
    window = MainWindow()
    snapshot = demo_snapshot()
    window.update_snapshot(snapshot)
    page = window.pages['arms']
    page.selector.buttons['right'].click()
    assert page.stack.currentWidget() is page.arms['right']
    detail = page.arms['right'].details
    detail.toggle.click()
    assert not detail.content.isHidden()
    assert window._snapshot is snapshot
    assert snapshot.right.adapter.state == 'ARMED'
    window.close()


def test_long_diagnostics_wrap_without_expanding_minimum_window(application):
    window = MainWindow()
    window.resize(1280, 720)
    base = demo_snapshot()
    reason = 'input_not_fresh: 等待控制器输入恢复 ' * 20
    snapshot = replace(base, left=replace(base.left,
        adapter=replace(base.left.adapter, state='FAULT', reason=reason)),
        linkerhand=replace(base.linkerhand, error=reason, state='COMM_ERROR'))
    window.update_snapshot(snapshot)
    window.show()
    for key in PAGE_KEYS:
        window.set_page(key)
        application.processEvents()
        page = window.pages[key]
        assert window.width() == 1280
        assert page.widget().width() <= page.viewport().width()
    window.close()


def test_pressed_controller_buttons_are_blue_inputs_and_stale_clears_them(application):
    window = MainWindow()
    base = demo_snapshot()
    pressed = replace(base.right_controller, button_lower=True, button_upper=True)
    window.update_snapshot(replace(base, right_controller=pressed))
    card = window.pages['controllers'].controllers['right']
    assert all(button.pressed for button in card.buttons)
    stale = replace(pressed, inputs_health=StreamHealth('STALE', 500, 0))
    window.update_snapshot(replace(base, right_controller=stale))
    assert all(not button.pressed and not button.available for button in card.buttons)
    assert all(bar.property('tone') == 'grey' for bar, _ in card.analogs)
    window.close()
