"""Offscreen behavior smoke tests; no ROS or robot is started."""

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

qt_package = pytest.importorskip("PyQt5")
# Some Windows PyQt wheels derive qt.conf with ANSI replacement characters in
# non-ASCII virtualenv paths. Explicit discovery keeps offscreen smoke portable.
if os.name == "nt":
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(
        Path(qt_package.__file__).parent / "Qt5" / "plugins" / "platforms"))

from PyQt5.QtWidgets import QApplication, QPushButton
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtCore import Qt

from rm65_teleop_dashboard.demo_data import demo_snapshot
from rm65_teleop_dashboard.main_window import MainWindow
from rm65_teleop_dashboard.models import StreamHealth


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    if os.name == "nt" and not QFontDatabase().families():
        for font_file in ("msyh.ttc", "segoeui.ttf", "consola.ttf"):
            path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font_file
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
    return app


def test_demo_monitor_opens_updates_and_closes(application):
    window = MainWindow()
    window.update_snapshot(demo_snapshot(1.0))
    window.show()
    application.processEvents()
    assert window.isVisible()
    assert "双臂机器人遥操作监控系统" in window.windowTitle()
    assert window.demo_badge.isVisible()
    arms = window.pages['arms'].arms
    assert arms['left'].state_label.text() == "ACTIVE"
    assert arms['right'].state_label.text() == "ARMED"
    assert len(arms['left'].joint_rows) == 6
    assert len(arms['right'].joint_rows) == 6
    assert not window.findChildren(QPushButton)
    window.close()
    application.processEvents()
    assert not window.isVisible()


@pytest.mark.parametrize("size", ((1920, 1080), (1600, 900), (1366, 768), (1280, 720)))
def test_monitor_fits_supported_window_sizes(application, size):
    window = MainWindow()
    window.resize(*size)
    window.update_snapshot(demo_snapshot(1.0))
    window.show()
    application.processEvents()
    assert (window.width(), window.height()) == size
    assert window.centralWidget().width() <= window.width()
    assert window.stack.width() <= window.width()
    for key in window.pages:
        window.set_page(key)
        application.processEvents()
        area = window.pages[key]
        assert area.widget().width() <= area.viewport().width()
    assert not window.grab().isNull()
    window.close()


def test_stale_adapter_cannot_display_live_active_or_ready(application):
    snapshot = demo_snapshot(1.0)
    left = replace(snapshot.left, status_health=StreamHealth("STALE", 1100, 10.0))
    window = MainWindow()
    window.update_snapshot(replace(snapshot, left=left))
    arm = window.pages['arms'].arms['left']
    assert arm.state_label.text() == "STALE"
    assert "READY" not in arm.cart.text().upper()
    assert "READY" not in arm.home.text().upper()
    assert window.pages['safety'].sections['left'].settings.fields["command_path_ready"].text() == "STALE"
    window.close()


def test_event_filter_renders_only_selected_level(application):
    from rm65_teleop_dashboard.models import EventRecord
    snapshot = replace(demo_snapshot(1.0), events=(
        EventRecord(1700000000, "INFO", "left_arm", "ACTIVE"),
        EventRecord(1700000001, "WARN", "safety", "input_not_fresh"),
        EventRecord(1700000002, "ERROR", "right_arm", "FAULT"),
    ))
    window = MainWindow()
    window.update_snapshot(snapshot)
    page = window.pages['events']
    window.set_page('events')
    assert page.table.rowCount() == 3
    page.filter.select("Warning")
    assert page.table.rowCount() == 1
    assert page.table.item(0, 1).data(Qt.UserRole) == "WARN"
    page.filter.select("Info")
    assert page.table.rowCount() == 1
    assert page.table.item(0, 1).data(Qt.UserRole) == "INFO"
    page.filter.select("All")
    assert page.table.rowCount() == 3
    window.close()
