from pathlib import Path
import shlex
import pytest
from rm65_teleop_dashboard.process_environment import discover_setup, sourced_command, SubprocessRunner
from rm65_teleop_dashboard.process_environment import environment_packages
from rm65_teleop_dashboard.process_environment import hand_sdk_available


def test_setup_discovery_respects_explicit_and_current_install_prefix(tmp_path):
    install = tmp_path / 'install with spaces'
    install.mkdir()
    setup = install / 'setup.bash'
    setup.write_text('# setup')
    assert discover_setup({'TELEOP_WORKSPACE_SETUP': str(setup)}) == setup
    assert discover_setup({'AMENT_PREFIX_PATH': str(install / 'rm65_teleop_dashboard')}) == setup
    with pytest.raises(RuntimeError):
        discover_setup({'TELEOP_WORKSPACE_SETUP': str(install / 'missing.bash')})


def test_shell_quote_paths_and_arguments_without_shell_injection():
    setup = Path("/tmp/workspace $(touch BAD)/install/setup.bash")
    command = sourced_command(('ros2', 'launch', 'pkg', 'entry.launch.py'), setup)
    assert command[:2] == ('/bin/bash', '-lc')
    assert shlex.quote(str(setup)) in command[2]
    assert 'exec ros2 launch pkg entry.launch.py' in command[2]
    assert '/usr/bin' in command[2]


def test_real_runner_refuses_windows(monkeypatch):
    monkeypatch.setattr('rm65_teleop_dashboard.process_environment.sys.platform', 'win32')
    with pytest.raises(RuntimeError, match='Ubuntu'):
        SubprocessRunner({}).start(('ros2', 'launch', 'anything'))


def test_overlay_missing_launch_cannot_fall_back_to_underlay(tmp_path):
    import os
    roots = [tmp_path / name for name in ('overlay', 'underlay')]
    for root in roots:
        for name in ('quest2ros', 'ros_tcp_endpoint', 'q2r2_bringup', 'rm65_teleop_adapter'):
            marker = root / 'share/ament_index/resource_index/packages' / name
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
    launch = roots[1] / 'share/rm65_teleop_adapter/launch/dual_quest_teleop.launch.py'
    launch.parent.mkdir(parents=True)
    launch.touch()
    assert not environment_packages({'AMENT_PREFIX_PATH': os.pathsep.join(map(str, roots))})[0]


def test_hand_sdk_check_reads_installed_node_default_without_importing_sdk(tmp_path):
    prefix, sdk = tmp_path / 'install', tmp_path / 'sdk'
    marker = prefix / 'share/ament_index/resource_index/packages/rm65_teleop_adapter'
    marker.parent.mkdir(parents=True)
    marker.touch()
    node = prefix / 'lib/rm65_teleop_adapter/right_linkerhand_node'
    node.parent.mkdir(parents=True)
    node.write_text('DEFAULT_SDK_PATH = ' + repr(str(sdk)) + '\nraise RuntimeError("never import this")', encoding='utf-8')
    env = {'AMENT_PREFIX_PATH': str(prefix)}
    assert not hand_sdk_available(env)
    transport = sdk / 'LinkerHand/core/rs485/realman_modbus.py'
    transport.parent.mkdir(parents=True)
    transport.touch()
    assert hand_sdk_available(env)
