# rm65_teleop_adapter

B-side safety adapter for Quest right-hand translation to the right RealMan RM65.

## Unified right-arm bringup

The unified launch starts the ROS TCP endpoint, Quest right-target bridge,
adapter, and read-only status monitor. It defaults to dry-run and does not
create RM65 hardware command publishers.

Dry-run:

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py
```

Hardware mode:

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py mode:=hardware
```

## Motion profiles

The unified launch accepts `motion_profile:=safe|normal|fast`. The default is
always `safe`.

| Profile | translation scale | max velocity | max step | max anchor distance | Status |
|---|---:|---:|---:|---:|---|
| `safe` | 0.2 | 0.005 m/s | 0.00005 m | 0.03 m | Default; existing real-hardware baseline parameters |
| `normal` | 0.5 | 0.020 m/s | 0.00010 m | 0.10 m | First tuning candidate; pending real-hardware feel validation |
| `fast` | 0.5 | 0.040 m/s | 0.00020 m | 0.10 m | Implemented / unvalidated on real hardware |

Hardware mode loads the safety base first and the selected motion override
second:

```text
config/hardware.yaml
+ config/motion_profiles/<motion_profile>.yaml
```

Motion profiles can override only `translation_scale`, `max_velocity_mps`,
`max_step_m`, and `max_anchor_distance_m`. Hardware gates, mapping, watchdogs,
workspace, control timing, follow/stop behavior, and topic names remain in
`hardware.yaml`.

Normal profile:

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py \
  mode:=hardware motion_profile:=normal
```

Fast profile:

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py \
  mode:=hardware motion_profile:=fast
```

Omitting `motion_profile` is equivalent to `motion_profile:=safe`. An invalid
value fails launch; it never falls back silently. In `mode:=dry_run`, the
adapter continues to load only `dry_run.yaml`, regardless of the selected
motion profile, and does not create hardware command publishers.

Hardware mode with RViz:

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py \
  mode:=hardware \
  use_rviz:=true
```

RViz can also be used in dry-run with `mode:=dry_run use_rviz:=true`. Its
minimal configuration uses `world` as the fixed frame and displays
`/quest_right_target_marker` and `/quest_right_target_pose`.

Available switches are `start_tcp`, `start_bridge`, `start_status`, and
`start_rm_driver`. The first three default to `true`; `start_rm_driver`
defaults to `false`.

`start_rm_driver:=true` is intentionally unsupported and fails safely. The
installed RM driver has a dual-arm launch and a generic single-arm launch that
does not use the verified right-arm configuration/namespace. Until a verified
right-only launch exists, start the right RM65 driver separately using the
known-good site procedure before selecting `mode:=hardware`. Do not start a
second driver when one is already running.

The status monitor only observes topics; it never publishes robot state or
commands. It prints immediately when the summary changes and otherwise about
once per second, for example:

```text
[teleop] QUEST=OK INPUTS=OK TARGET=OK ROBOT=OK STATE=ARMED DEADMAN=OFF CMD=OK
```

Malformed or stale adapter status is shown as `STATE=UNKNOWN` rather than
terminating the monitor. Monitor freshness is display-only and is not part of
the adapter safety state machine.

The adapter supports two explicit modes:

- dry-run: preview and status only; no hardware command publishers are created;
- hardware: requires `dry_run=false`, `hardware_write_enabled=true`, and
  `mapping_verified=true` before command publishers are created.

The first-stage enable source is `/q2r_right_hand_inputs.button_lower`. The
adapter independently watches target, raw Quest Pose, Inputs, robot feedback,
command-path uniqueness, and control-cycle timing. Release or any timeout stops
new CANFD points, publishes repeated `move_stop_cmd`, and requires a fresh
release-to-press sequence with new Quest and robot anchors.

The field-verified physical mapping is:

```text
Quest +X forward -> RM65 -Y
Quest +Y left    -> RM65 -Z
Quest +Z up      -> RM65 +X
```

Commands are relative to double anchors. Quest absolute position and orientation
are never sent to the robot; phase 1 keeps the robot anchor orientation fixed.
The checked-in hardware base uses `follow=false`, a nominal 200 Hz timer, and a
50 ms control-stall fault. The default `safe` motion profile adds the 5 mm/s
velocity limit, 0.05 mm per-step limit, and 3 cm anchor radius. Dry-run remains
the default launch mode.

## Build and test

```bash
source /opt/ros/humble/setup.bash
source /home/lh/robot/install/setup.bash
colcon build --packages-select rm65_teleop_adapter
colcon test --packages-select rm65_teleop_adapter
colcon test-result --verbose
```

## Run dry-run

```bash
source install/setup.bash
export ROS_DOMAIN_ID=42
ros2 launch rm65_teleop_adapter dry_run.launch.py
```

The legacy single-node launch above remains available. Prefer the unified
bringup command for routine Quest teleoperation setup.

Simulation publishers must be remapped to test-only topics; do not inject simulated data into live Quest topics.

## Run hardware mode

Only after the right-arm driver, workspace, emergency stop, unique command source,
and live Quest inputs have been checked:

```bash
ros2 launch rm65_teleop_adapter hardware.launch.py
```

This bringup/observability change was validated without starting or commanding
a real RM65. It does not replace the existing hardware safety gates or a future
on-robot acceptance run.
