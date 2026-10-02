"""Screenshot page selection is validated before Qt or ROS starts."""
import pytest
import os
from pathlib import Path
import struct
import subprocess
import sys
from rm65_teleop_dashboard.app import argument_parser
from rm65_teleop_dashboard.view_config import PAGE_KEYS


def test_page_argument_accepts_six_pages_and_rejects_invalid():
    parser = argument_parser()
    assert parser.parse_args(['--demo']).page == 'overview'
    for page in ('overview', 'arms', 'controllers', 'safety', 'linkerhand', 'events'):
        assert parser.parse_args(['--demo', '--page', page]).page == page
    with pytest.raises(SystemExit) as error:
        parser.parse_args(['--demo', '--page', 'invalid'])
    assert error.value.code == 2


def cli_environment():
    env = os.environ.copy()
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
    return env


@pytest.mark.parametrize('page', PAGE_KEYS)
def test_demo_cli_captures_each_page_without_ros(page, tmp_path):
    pytest.importorskip('PyQt5')
    target = tmp_path / (page + '.png')
    result = subprocess.run([sys.executable, '-m', 'rm65_teleop_dashboard.app',
        '--demo', '--page', page, '--width', '1280', '--height', '720',
        '--screenshot', str(target)], env=cli_environment(), capture_output=True, timeout=25)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    payload = target.read_bytes()
    assert payload[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', payload[16:24]) == (1280, 720)
    assert b'Screenshot:' in result.stdout


def test_invalid_page_cli_exits_before_loading_gui_or_ros():
    result = subprocess.run([sys.executable, '-m', 'rm65_teleop_dashboard.app',
        '--page', 'robot-control'], env=cli_environment(), capture_output=True, timeout=10)
    assert result.returncode == 2
    assert b'invalid choice' in result.stderr
    assert b'ROS mode requires' not in result.stderr
