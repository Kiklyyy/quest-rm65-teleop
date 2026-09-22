# rm65_teleop_adapter

B-side safety adapter for Quest right-hand 6DoF pose teleoperation to the right RealMan RM65.

## Unified right-arm bringup

The unified launch starts the ROS TCP endpoint, Quest right-target bridge,
adapter, and read-only status monitor. It defaults to dry-run and does not
create RM65 hardware command publishers.

Dry-run:

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py
```

Hardware mode (translation has prior field evidence; orientation does not):

> **Hardware warning:** Automated success does not authorize real robot rotation.
> Complete the live Quest probe and obtain explicit authorization for staged RM65 validation first.

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py mode:=hardware
```

## Motion profiles

The unified launch accepts `motion_profile:=safe|normal|fast`. The default is
always `safe`.

| Profile | translation scale | max velocity | max step | max anchor distance | Status |
|---|---:|---:|---:|---:|---|
| `safe` | 0.2 | 0.005 m/s | 0.00005 m | 0.03 m | Default; existing real-hardware baseline parameters |
| `normal` | 1.0 | 0.20 m/s | 0.00050 m | 1.0 m | Real Quest → right RM65 feel-tested tuning value |
| `fast` | 0.5 | 0.040 m/s | 0.00020 m | 0.10 m | Experimental; not for hardware use yet |

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

Normal profile hardware example:

> **Hardware warning:** The `normal` translation tuning evidence does not verify
> orientation; automated success does not authorize real robot rotation.

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py \
  mode:=hardware motion_profile:=normal
```

The current `normal` values were tested onsite with a real Quest and the real
right RM65. The operator reported clearly improved responsiveness and a more
reasonable translation range, with the larger per-step limit producing the
most noticeable improvement. This was a qualitative feel test, not a
measurement of exact speed, stopping distance, overshoot, or long-duration
stability.

At the nominal 200 Hz control rate, the 0.0005 m step limit gives a theoretical
upper bound of about 0.10 m/s; this is not a measured speed. The 1.0 m anchor
radius is a field-tested tuning value pending workspace and stopping-margin
review, not a recommended safety boundary.

Fast profile hardware example:

> **Hardware warning:** `fast` is unverified for hardware use, and automated
> orientation success does not authorize real robot rotation.

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py \
  mode:=hardware motion_profile:=fast
```

`fast` has not been tested on a real arm. It is experimental and should not be
used to start or control real hardware yet.

Omitting `motion_profile` is equivalent to `motion_profile:=safe`. An invalid
value fails launch; it never falls back silently. In `mode:=dry_run`, the
adapter continues to load only `dry_run.yaml`, regardless of the selected
motion profile, and does not create hardware command publishers.

Hardware mode with RViz:

> **Hardware warning:** RViz preview is not hardware validation; automated
> success does not authorize real robot rotation.

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

The enable source is `/q2r_right_hand_inputs.press_middle`. The
middle-grip analog value uses hysteresis: values at or above `0.60` turn the
deadman on, values at or below `0.40` turn it off, and values strictly between
the thresholds preserve the previous state. NaN or infinite values safely turn
the deadman off. `button_lower` no longer controls right-arm teleoperation, and
`press_index` remains unused.

The adapter status JSON publishes `deadman_pressed` and
`deadman_source="press_middle"`. The read-only monitor displays this semantic
state as `DEADMAN=ON/OFF` and accepts legacy `button_lower` status only as a
fallback for old adapter data.

The adapter independently watches target, raw Quest Pose, Inputs, robot
feedback, command-path uniqueness, and control-cycle timing. Release or any
timeout stops new CANFD points, publishes repeated `move_stop_cmd`, and requires
a fresh release-to-press sequence with new Quest and robot anchors.

The field-verified physical mapping is:

```text
Quest +X forward -> RM65 -Y
Quest +Y left    -> RM65 -Z
Quest +Z up      -> RM65 +X
```

Commands are relative to position and orientation anchors. Pressing the
middle-finger Grip captures both Quest and robot anchors; translation and
rotation are computed together and committed as one Pose. Releasing Grip stops
teleoperation, and pressing again captures fresh anchors without a command jump.
Quest absolute pose is never copied directly to the robot.

Raw Quest orientation comes directly from
`/q2r_right_hand_pose.pose.orientation`; the identity orientation carried by
`/quest_right_target_pose` remains a translation-bridge placeholder. The
implemented world-frame convention is:

```text
Delta R_Q = R_Q * R_Q0^T
Delta R_Q_scaled = shortest-axis-angle-scale(Delta R_Q, rotation_scale)
Delta R_RM = M * Delta R_Q_scaled * M^T
R_desired = Delta R_RM * R_R0
```

The first orientation safety envelope is:

| Parameter | Code/config value | Human-readable value |
|---|---:|---:|
| `rotation_scale` | `1.0` | one-to-one relative angle |
| `max_angular_velocity_rad_s` | `1.5707963267948966` | 90 deg/s |
| `max_angular_step_rad` | `0.01` | about 0.57 deg/cycle |
| `max_anchor_angle_rad` | `1.5707963267948966` | 90 deg |
| `unexpected_orientation_jump_rad` | `0.7853981633974483` | 45 deg |

Angular output advances from the last command by shortest-path SLERP with
`min(max_angular_step_rad, max_angular_velocity_rad_s * dt)`. Invalid or
non-finite Quest/robot quaternions, an above-threshold consecutive Quest jump,
or an above-limit anchor-relative angle stop the whole Pose command and require
the existing fault/rearm sequence. Quaternion sign flips (`q` to `-q`) are
the same orientation and do not create a jump.

The checked-in hardware base uses `follow=false`, a nominal 200 Hz timer, and a
50 ms control-stall fault. The default `safe` motion profile adds the 5 mm/s
velocity limit, 0.05 mm per-step limit, and 3 cm anchor radius. Translation
mapping, motion profiles, workspace, deadman thresholds, watchdogs and command
path remain unchanged. Dry-run remains the default launch mode.

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

The bounded adapter-only 6DoF synthetic probe uses an isolated local ROS domain:

```bash
export ROS_DOMAIN_ID=142
export ROS_LOCALHOST_ONLY=1
install/rm65_teleop_adapter/lib/rm65_teleop_adapter/rm65_teleop_adapter_node \
  --ros-args \
  --params-file install/rm65_teleop_adapter/share/rm65_teleop_adapter/config/dry_run.yaml &
adapter_pid=$!
/usr/bin/python3 src/rm65_teleop_adapter/test/dry_run_6dof_probe.py
kill "$adapter_pid"
wait "$adapter_pid" 2>/dev/null || true
```

This probe verifies software preview behavior and zero hardware-command
publishers only. Live Quest quaternion probing and real RM65 rotation remain
pending.

## Run hardware mode

Only after the right-arm driver, workspace, emergency stop, unique command source,
and live Quest inputs have been checked:

> **Hardware warning:** Automated and synthetic dry-run success does not
> authorize real robot rotation. Live Quest validation and an explicitly
> authorized staged RM65 procedure are still required.

```bash
ros2 launch rm65_teleop_adapter hardware.launch.py
```

The translation path and the current `normal` tuning have received qualitative
real Quest → right RM65 testing. This does not replace the existing hardware
safety gates or a systematic on-robot acceptance run. `fast` remains
unvalidated and is not for real-hardware use yet.
