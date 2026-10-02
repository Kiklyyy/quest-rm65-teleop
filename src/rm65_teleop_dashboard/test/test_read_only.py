"""Prevent output endpoint or hardware-launch regressions."""
import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_runtime_source_has_no_control_capability():
    forbidden = {
        'create_publisher', 'create_service', 'create_client', 'ActionClient',
        'FollowJointTrajectory', 'movep_canfd', 'movej_canfd', 'move_stop_cmd',
        'finger_move',
    }
    for source in (ROOT / 'rm65_teleop_dashboard').rglob('*.py'):
        tree = ast.parse(source.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id not in forbidden, source
            elif isinstance(node, ast.Attribute):
                assert node.attr not in forbidden, source
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any(word in node.value for word in forbidden), source


def test_launch_starts_dashboard_alone_and_defaults_to_real_monitoring():
    source = (ROOT / 'launch/dashboard.launch.py').read_text(encoding='utf-8')
    assert "default_value='false'" in source
    assert "package='rm65_teleop_dashboard'" in source
    for name in ('IncludeLaunchDescription', 'rm_driver', 'rm_control', 'linker_hand_api'):
        assert name not in source
