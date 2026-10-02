"""Desktop entry point. Demo works without importing ROS or the hand SDK."""
import argparse
from dataclasses import replace
import os
from pathlib import Path
import signal
import sys
import time
from .view_config import PAGE_KEYS


def argument_parser():
    parser = argparse.ArgumentParser(description='Read-only Dual-Arm VR Teleoperation Dashboard')
    parser.add_argument('--demo', action='store_true', help='Clearly labelled synthetic data, no ROS')
    parser.add_argument('--screenshot', type=Path, help='Save a PNG after one second, then exit')
    parser.add_argument('--page', choices=PAGE_KEYS, default='overview', help='Initial monitoring page')
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    return parser


def main(args=None):
    raw = list(sys.argv[1:] if args is None else args)
    ros_args = []
    if '--ros-args' in raw:
        boundary = raw.index('--ros-args')
        ros_args, raw = raw[boundary:], raw[:boundary]
    parser = argument_parser()
    options = parser.parse_args(raw)
    if options.width < 1280 or options.height < 720:
        parser.error('window size must be at least 1280 x 720')
    if not options.demo and os.path.realpath(sys.executable) != os.path.realpath('/usr/bin/python3'):
        print('ROS mode requires /usr/bin/python3 (Ubuntu 22.04 / ROS 2 Humble).', file=sys.stderr)
        return 2
    try:
        import PyQt5
        # Some Windows Qt 5 builds lose non-ASCII components in their compiled
        # plugin search path. Locate installed local plugins from Python instead.
        if os.name == 'nt':
            plugins = Path(PyQt5.__file__).parent / 'Qt5' / 'plugins' / 'platforms'
            if plugins.is_dir():
                os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', str(plugins))
        from PyQt5.QtCore import QTimer, Qt
        from PyQt5.QtGui import QFontDatabase
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print('Missing PyQt5. On Ubuntu use: sudo apt install python3-pyqt5', file=sys.stderr)
        return 2
    from .demo_data import demo_snapshot
    from .main_window import MainWindow
    from .models import EventLogger, SnapshotStore

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication([sys.argv[0]])
    if os.name == 'nt' and not QFontDatabase().families():
        # Windows offscreen may not enumerate fonts. Reuse installed system
        # fonts; normal desktop and Ubuntu keep their usual font discovery.
        font_dir = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for font_name in ('msyh.ttc', 'segoeui.ttf', 'consola.ttf'):
            font_path = font_dir / font_name
            if font_path.is_file():
                QFontDatabase.addApplicationFont(str(font_path))
    app.setApplicationName('Dual-Arm VR Teleoperation Dashboard')
    window = MainWindow()
    window.resize(options.width, options.height)
    window.set_page(options.page)
    domain = os.environ.get('ROS_DOMAIN_ID', '0')
    store = SnapshotStore(domain_id=domain)
    monitor = None
    if not options.demo:
        try:
            from .ros_monitor import RosMonitorRuntime
            monitor = RosMonitorRuntime(store, ros_args=ros_args)
            monitor.start()
        except (ImportError, RuntimeError) as exc:
            print(f'Cannot start ROS monitoring: {exc}. Source the Humble and workspace setup files.',
                  file=sys.stderr)
            return 2
    started = time.monotonic()
    events = EventLogger()
    exit_code = [0]

    def refresh():
        snapshot = (demo_snapshot(time.monotonic() - started, domain_id=domain)
                    if options.demo else store.snapshot())
        window.update_snapshot(replace(snapshot, events=events.update(snapshot)))

    def capture():
        try:
            options.screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(options.screenshot), 'PNG'):
                raise OSError('Qt could not save the PNG')
            print(f'Screenshot: {options.screenshot.resolve()}')
        except OSError as exc:
            print(f'Screenshot failed: {exc}', file=sys.stderr)
            exit_code[0] = 1
        app.quit()

    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(refresh)
    refresh()
    timer.start()
    window.show()
    if options.screenshot:
        QTimer.singleShot(1100, capture)
    previous_signals = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_signals[signum] = signal.signal(signum, lambda *_: app.quit())
    try:
        result = app.exec_()
    finally:
        timer.stop()
        if monitor is not None:
            monitor.stop()
        for signum, handler in previous_signals.items():
            signal.signal(signum, handler)
    return exit_code[0] or result


if __name__ == '__main__':
    sys.exit(main())
