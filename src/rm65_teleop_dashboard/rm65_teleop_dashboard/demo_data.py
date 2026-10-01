"""Self-contained synthetic display data; never sent into ROS."""
import math
import time

from .models import (
    AdapterStatus, ArmSnapshot, ControllerSnapshot, LinkerHandSnapshot,
    StreamHealth, SystemSnapshot, finite_number, pose_snapshot,
)


def _quaternion(roll, pitch, yaw):
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)


def _pose(x, y, z, roll, pitch, yaw):
    return pose_snapshot((x, y, z), _quaternion(roll, pitch, yaw))


def demo_snapshot(elapsed_s=0.0, domain_id="42"):
    """Deterministic motion at a given elapsed time with explicit DEMO marker."""
    if not finite_number(elapsed_s) or elapsed_s < 0:
        raise ValueError("elapsed_s must be finite and nonnegative")
    t = float(elapsed_s)
    controller_health = StreamHealth("ONLINE", 12.0, 72.0)
    inputs_health = StreamHealth("ONLINE", 9.0, 72.0)
    feedback_health = StreamHealth("ONLINE", 4.0, 198.0)
    status_health = StreamHealth("ONLINE", 38.0, 10.0)
    target_health = StreamHealth("ONLINE", 8.0, 50.0)
    left_pose = _pose(.432 + .018 * math.sin(t * .6), -.218 + .010 * math.cos(t * .5),
                      .556 + .008 * math.sin(t * .4), 3.08, -.18, .4 + .05 * math.sin(t))
    right_pose = _pose(-.428, .225, .542, -3.1, -.17, -1.5)
    # These are simulated healthy hardware telemetry values. SystemSnapshot.demo
    # always identifies the data source; this module never connects to ROS.
    common_status = dict(dry_run=False, hardware_write_enabled=True,
        hardware_output_available=True, mapping_verified=True, deadman_source="press_middle",
        target_fresh=True, quest_pose_fresh=True, inputs_fresh=True, home_inputs_fresh=True,
        robot_fresh=True, joint_state_fresh=True, quest_pose_age_ms=12.0, inputs_age_ms=9.0,
        joint_preset_x_inputs_age_ms=9.0, robot_age_ms=4.0, joint_state_age_ms=4.0,
        rearm_count=0, watchdog_count=0, home_button_pressed=False,
        joint_preset_selection="NONE", joint_preset_active="NONE", home_hold_progress=0.0,
        home_action_state="IDLE", command_path_ready=True, home_command_path_ready=True,
        max_cycle_period_ms=6.2)
    left = ArmSnapshot(side="left", robot_pose=left_pose, target_pose=left_pose,
        joints_deg=tuple(base + 2 * math.sin(t * .5 + index * .6)
                         for index, base in enumerate((-88.4, -7.4, -61.2, -3.6, -36.8, 99.2))),
        adapter=AdapterStatus(state="ACTIVE", deadman_pressed=True, joint_presets_enabled=False,
                              **common_status), robot_health=feedback_health,
        joints_health=feedback_health, target_health=target_health, status_health=status_health)
    right = ArmSnapshot(side="right", robot_pose=right_pose, target_pose=right_pose,
        joints_deg=(69.095, -32.717, 95.243, 34.124, 37.393, 159.266),
        adapter=AdapterStatus(state="ARMED", deadman_pressed=False, joint_presets_enabled=True,
                              **common_status), robot_health=feedback_health,
        joints_health=feedback_health, target_health=target_health, status_health=status_health)
    left_controller = ControllerSnapshot(
        pose=_pose(.12 + .012 * math.sin(t * .6), 1.34, .98, .22, -.09, 3.08),
        grip=.76 + .08 * math.sin(t), trigger=.18 + .10 * (1 + math.sin(t * .7)) / 2,
        button_lower=False, button_upper=False, pose_health=controller_health,
        inputs_health=inputs_health)
    right_controller = ControllerSnapshot(
        pose=_pose(-.15, 1.31, 1.02, -.2, -.11, -3.12),
        grip=.22, trigger=.15 + .78 * (1 + math.sin(t * .8)) / 2,
        button_lower=False, button_upper=False, pose_health=controller_health,
        inputs_health=inputs_health)
    closed = int(t // 5) % 2 == 1
    target = (73, 0, 0, 0, 0, 0, 156) if closed else (73, 0, 255, 255, 255, 255, 156)
    hand = LinkerHandSnapshot(state="READY", trigger_value=right_controller.trigger,
        trigger_pressed=right_controller.trigger >= .6, trigger_armed=right_controller.trigger <= .4,
        hand_toggle_state="CLOSED" if closed else "OPEN", target=target, actual=target,
        fault_codes=(0,) * 7, communication_ok=True, input_fresh=True, dry_run=False,
        connect_only=False, invalid_input_count=0, health=status_health)
    return SystemSnapshot(left=left, right=right, left_controller=left_controller,
        right_controller=right_controller, linkerhand=hand, demo=True,
        domain_id=str(domain_id), node_count=12, time_s=time.time())
