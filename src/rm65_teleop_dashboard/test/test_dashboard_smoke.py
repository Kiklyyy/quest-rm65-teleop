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
    assert window.left_arm.state_label.text() == "ACTIVE"
    assert window.right_arm.state_label.text() == "ARMED"
    assert len(window.left_arm.joint_rows) == 6
    assert len(window.right_arm.joint_rows) == 6
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
    assert window.columns.width() <= window.width()
    for index in (0, 2):
        area = window.columns.widget(index)
        assert area.widget().width() <= area.viewport().width()
    assert not window.grab().isNull()
    window.close()


def test_stale_adapter_cannot_display_live_active_or_ready(application):
    snapshot = demo_snapshot(1.0)
    left = replace(snapshot.left, status_health=StreamHealth("STALE", 1100, 10.0))
    window = MainWindow()
    window.update_snapshot(replace(snapshot, left=left))
    assert window.left_arm.state_label.text() == "STALE"
    assert "READY" not in window.left_arm.cart.text()
    assert "READY" not in window.left_arm.home.text()
    assert window.safety_card.fields["command_path_ready"][0].text() == "STALE"
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
    assert window.events_table.rowCount() == 3
    window.log_filter.setCurrentText("Warning")
    assert window.events_table.rowCount() == 1
    assert window.events_table.item(0, 1).text() == "WARN"
    window.log_filter.setCurrentText("All")
    assert window.events_table.rowCount() == 3
    window.close()
