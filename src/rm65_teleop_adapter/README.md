# rm65_teleop_adapter

Safety adapter for one Quest hand and its corresponding RealMan RM65 per process.

## One-command dual-arm bringup

`dual_quest_teleop.launch.py` combines the verified dual RM65 driver launch,
dual `rm_control` launch, one shared Quest TCP endpoint, both target bridges,
both teleop adapters, both status monitors, and the optional right O7 hand.
Dry-run is the safe default and does not start either RM driver or controller:

```bash
ros2 launch rm65_teleop_adapter dual_quest_teleop.launch.py
```

Hardware launch with both RM65 drivers/controllers and both Quest adapters:

```bash
ros2 launch rm65_teleop_adapter dual_quest_teleop.launch.py \
  mode:=hardware motion_profile:=normal
```

The parent launch uses `rm_65_dual_driver.launch.py` and
`rm_65_dual_control.launch.py`, matching the known left `.18:8089` and right
`.19:8090` configuration. It starts the ROS TCP endpoint only through the
right child; the left child always receives `start_tcp:=false`. If either RM
stack is already running, use `start_drivers:=false` and/or
`start_controls:=false` to avoid duplicate graph owners.

The right O7 tool-RS485 node remains explicit opt-in:

```bash
ros2 launch rm65_teleop_adapter dual_quest_teleop.launch.py \
  mode:=hardware motion_profile:=normal start_linkerhand:=true
```

> **Hardware warning:** right RM driver + O7 API2 coexistence is not yet
> accepted for routine operation. An onsite A/B test correlated enabling the
> hand SDK with a first-Grip old-pose jump on the right arm. The unified launch
> therefore keeps `start_linkerhand:=false` by default. Do not run the final
> command until the staged coexistence diagnosis has passed with an operator
> at the stop control.

## Unified right-arm bringup

The unified launch starts the ROS TCP endpoint, Quest right-target bridge,
adapter, and read-only status monitor. It defaults to dry-run and does not
create RM65 hardware command publishers.

Dry-run:

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py
```

Hardware mode (right Home execution and B-release cancel hardware validated):

> **Hardware warning:** Quest pose and inputs can still have simultaneous gaps beyond the 200 ms watchdog timeout. Check current input freshness and command-path ownership before hardware use.

```bash
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py mode:=hardware
```

## Shared left/right executable and left hardware mode

The same adapter executable and safety state machine serve one configured arm
per process. Explicit `expected_adapter_node`, `expected_driver_node`, and
`expected_control_node` identities gate command graph ownership. Right YAML
retains all existing right endpoints and hardware Home settings. The new
`left_dry_run.yaml` uses `/left` inputs/status/preview and the operator-derived
proper rotation mapping. It cannot write hardware or start Home.

```bash
export ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1
ros2 launch rm65_teleop_adapter left_quest_teleop.launch.py \
  mode:=dry_run use_rviz:=false start_tcp:=false
```

The left launch shares the parameterized Quest target bridge and read-only
monitor. `start_tcp` defaults to `false` to avoid taking a port already owned
by a live endpoint. Without fresh left robot feedback, the adapter remains
`DISABLED`; isolated tests provide synthetic feedback only in domain 143.
The single versioned `hardware.yaml` contains a ROS 2 `/**` common block plus
separate `rm65_teleop_adapter` and `left_rm65_teleop_adapter` blocks. Common
hardware gates, watchdogs, timing, limits and workspace are defined once;
endpoints, mappings, frames and Home targets remain arm-specific. The left
launch defaults to dry-run; the explicit hardware invocation uses the same
four normal motion values as the right arm without changing the right profile:

```bash
export ROS_DOMAIN_ID=42
ros2 launch rm65_teleop_adapter left_quest_teleop.launch.py \
  mode:=hardware motion_profile:=normal start_rm_driver:=false \
  use_rviz:=false start_tcp:=true
```

Start exactly one left-only RM driver separately, with namespace remap
`-r __ns:=/left` and no global `__node` remap. Keep left `rm_control` off for
Cartesian-only sessions. Start one left-only `rm_control` with Action
`/left/rm_group_controller/follow_joint_trajectory` for an explicit Home
hardware session, after checking command-path ownership.
The left hardware workspace matches the right numeric bounds
`[-1,-1,0]` to `[1,1,1.5]` m for the operator-authorized test; it is not a
final collision/workcell envelope. Right physical B and left physical Y each
hold their own arm's Home button for 1.5 s with Grip released; speed is
15 deg/s. Left Home target degrees, in joint1–joint6 order, are
`[-90.52991560598026,-7.43359734865227,-62.41522144150158,
-3.5143370089334374,-37.08400247904573,99.21228312734117]`.
Left X and gripper remain unbound. Left dry-run still has Home disabled and no
real Home Action client. The earlier `left_test` profile and local P0 workspaces
are retired. Quest input gaps remain an open issue, with the existing
watchdog/stop/rearm behavior unchanged. On 2026-09-26, left Y Home reached its
six-joint target within 0.023° and a separate mid-motion Y release ended with
adapter `CANCELED` and physical stopping before Home. Joint 3 still traveled
6.44° after release before stabilizing; the stopping margin remains open for
review. See `docs/progress/left-arm-teleop.md` for moving-hardware evidence.

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

> **Hardware warning:** The `normal` profile has qualitative feel-test evidence only; its exact speed, stopping margin, and long-duration stability remain unmeasured.

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

> **Hardware warning:** `fast` is unverified for hardware use. Quest/TCP input stability remains open.

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
[teleop] QUEST=OK INPUTS=OK TARGET=OK ROBOT=OK JOINTS=OK STATE=ARMED DEADMAN=OFF CMD=OK HOME=IDLE
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
`press_index` is not read by the arm adapter. An independent, opt-in right
LinkerHand L7 node uses it for hand opening and closing.

### Optional right LinkerHand L7 node

`right_quest_teleop.launch.py` defaults `start_linkerhand:=false`. Set it to
`true` for `/right_linkerhand` to subscribe to `/q2r_right_hand_inputs` and
publish `/right/linkerhand/status` (`std_msgs/msg/String` JSON). In
`mode:=dry_run`, it publishes only mapped targets and status. In
`mode:=hardware`, it instantiates the onsite right-L7 SDK through the RM65
tool RS485 port and writes changed targets at no more than 20 Hz. The SDK
instance belongs only to this process.
For coexistence diagnosis, `linkerhand_connect_only:=true` with hardware mode
still connects the SDK and polls feedback/faults but never calls `finger_move`.
Run `right_linkerhand_node` alone with `dry_run:=false`,
`hardware_write_enabled:=true`, and `connect_only:=true` when the arm adapter
must remain off. Status then reports `CONNECT_ONLY` and `target=null`.

`press_index >= 0.60` means pressed and `<= 0.40` means released.
Each armed released-to-pressed edge toggles between CLOSED
`[73,0,0,0,0,0,156]` (first press) and OPEN
`[73,0,255,255,255,255,156]` (second press). Startup does not send a hand
command; status `target` is null until the first press. Stale or non-finite
input holds the hand and requires a valid release before the next toggle.
Status JSON contains `stamp`, `trigger_value`, `trigger_pressed`,
`trigger_armed`, `hand_toggle_state`, seven-axis `target`/`actual`, raw
`fault_codes`, `communication_ok`, `input_fresh`, `dry_run`, `state`, and
`error`. Standalone SDK hardware operation was reported validated onsite;
the current toggle and dual-arm coexistence are pending hardware validation.

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

## Hold-to-run right Quest joint presets

The right adapter now maps three Quest face buttons to the three six-joint
targets stored under its own `hardware.yaml` section:

| Physical button | ROS input | Parameter |
|---|---|---|
| X | `/q2r_left_hand_inputs.button_lower` | `quest_right_first` |
| A | `/q2r_right_hand_inputs.button_lower` | `quest_right_second` |
| B | `/q2r_right_hand_inputs.button_upper` | `quest_right_last` |

The targets are ordered `joint1` through `joint6` in degrees. The old single
right B/Home target is superseded by these presets; the independent left Y/Home
target is unchanged. Grip `press_middle` remains the Cartesian teleop deadman.

Each preset reuses the existing guarded `FollowJointTrajectory` path. The
adapter must be `ARMED`, Grip must be released, both Quest input streams and
joint feedback must be fresh, and the right driver/control graph must have
exclusive ownership. Hold exactly one of X/A/B continuously for
`home_hold_seconds: 1.5`; simultaneous buttons or changing buttons without a
full release are rejected until all three are released. Releasing the selected
button during motion requests Action cancel plus repeated stop.

The generated trajectory retains the existing four-point smoothstep and
`home_speed_deg_s: 15.0` bound. JointState is reordered by name, and missing,
duplicate, non-finite or mismatched samples block the request. During the
joint action the adapter publishes no Cartesian `movep_canfd_cmd`. Completion
or acknowledged cancellation enters `REARM_REQUIRED`, followed by button and
Grip release before Cartesian teleop can resume.

Status JSON adds `home_inputs_fresh`, `joint_presets_enabled`,
`joint_preset_selection`, `joint_preset_active`, and X-input age. The isolated
test graph verifies the exact X/A/B final joint targets, cancel/watchdog paths,
zero Cartesian commands and zero real command publishers. These three new
targets have software-only validation; no real RM65 preset motion was started.

## Build and test

Use system Python and the isolated worktree:

```bash
conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /home/lh/robot/install/setup.bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
/usr/bin/colcon --log-base log build --build-base build --install-base install \
  --symlink-install --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter
/usr/bin/colcon --log-base log test --build-base build --install-base install \
  --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter \
  --event-handlers console_direct+
/usr/bin/colcon test-result --test-result-base build --all --verbose
```

Observed complete result after the 2026-09-24 Home target update: 206 tests, 0 errors, 0 failures, 0 skipped.

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

This older probe verifies software preview behavior and zero hardware-command
publishers only. Live Quest quaternion and qualitative real RM65 orientation
evidence are recorded in `STATUS.md`; subsequent right Home execution and
B-release cancel hardware validation are recorded in the Home progress document.

## Run hardware mode

Only after the right-arm driver, workspace, emergency stop, unique command source,
and live Quest inputs have been checked:

> **Hardware warning:** right Home execution and mid-motion B-release
> stop/cancel have been field-validated. Quest/TCP input dropouts beyond 200 ms
> remain an open stability issue; retain the existing freshness/rearm gates.

```bash
ros2 launch rm65_teleop_adapter hardware.launch.py
```

The translation path and the current `normal` tuning have received qualitative
real Quest → right RM65 testing. This does not replace the existing hardware
safety gates or a systematic on-robot acceptance run. `fast` remains
unvalidated and is not for real-hardware use yet.
