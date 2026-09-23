# Right-arm 6DoF orientation progress

## Scope and base

- Branch: `feat/quest-orientation`
- Ubuntu worktree: `/home/lh/quest2ros2_ws/.worktrees/quest-orientation`
- Main base: `f4693121c8a0943039d393323b2da44de985c56e`
- Design base: `9445bf54deef3a23fd14b0e267107bb309ca3ba5`
- Implementation plan: `42f77d32c37f0eb96bdc853277fac7ebf5d2ce76`
- Scope: right-arm relative orientation extension only; no gripper, left arm,
  dual arm, collision integration or task logic.

## Implemented architecture

The existing Quest translation bridge is unchanged:
`Quest position -> /quest_right_target_pose -> adapter translation`. Raw
`/q2r_right_hand_pose.pose.orientation` enters the adapter directly, where a
single orientation tracker feeds the existing safety-gated control timer.
Translation and rotation are committed atomically in the existing single Pose
command. No orientation-specific hardware publisher, timer or RM driver topic
was added.

Middle-finger Grip `press_middle` retains the 0.60/0.40 hysteresis. A press
captures Quest position/orientation and robot position/orientation anchors.
Release stops, and repress captures fresh anchors without a preview jump.

## Quaternion convention and equations

ROS storage is `(x, y, z, w)`. Math uses Hamilton products and active
column-vector rotations. Legal quaternions are normalized, `q` and `-q` are
treated as one orientation, relative angles and SLERP use the shortest path, and
Euler accumulation is not used.

```text
Delta R_Q = R_Q * R_Q0^T
Delta R_Q_scaled = shortest-axis-angle-scale(Delta R_Q, rotation_scale)
Delta R_RM = M * Delta R_Q_scaled * M^T
R_desired = Delta R_RM * R_R0

M = [ 0  0  1
     -1  0  0
      0 -1  0 ]
```

The robot anchor composition deliberately left-multiplies the RM-base/world
relative delta.

## Safety envelope

| Parameter | Value |
|---|---:|
| `rotation_scale` | `1.0` |
| `max_angular_velocity_rad_s` | `1.5707963267948966` |
| `max_angular_step_rad` | `0.01` |
| `max_anchor_angle_rad` | `1.5707963267948966` |
| `unexpected_orientation_jump_rad` | `0.7853981633974483` |

Each cycle advances by shortest-path SLERP with
`min(max_angular_step_rad, max_angular_velocity_rad_s * dt)`. Invalid Quest
orientation, invalid robot orientation, an above-threshold consecutive Quest
jump, or an above-limit anchor-relative angle stops the whole Pose command and
enters the existing fault/rearm flow. Exact 45 degree jumps and exact 90 degree
anchor deltas are allowed; strictly larger values fault. Deadman release remains
the highest-priority ACTIVE transition.

## Automated evidence

Task 6 complete four-package command:

```bash
/usr/bin/colcon --log-base log build \
  --build-base build --install-base install --symlink-install \
  --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter
/usr/bin/colcon --log-base log test \
  --build-base build --install-base install \
  --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter \
  --event-handlers console_direct+
/usr/bin/colcon test-result --test-result-base build --all --verbose
```

Fresh result: 166 tests, 0 errors, 0 failures, 0 skipped.

The focused Task 6 run executed
`test_quaternion_math`, `test_quest_orientation_tracker`,
`test_adapter_logic`, `test_adapter_config`, `test_input_deadman`, and
pytest over motion profiles, teleop status, Quest target logic and Quest target
bridge. Result: 73/73 focused C++ tests and 83/83 focused Python tests passed
(156/156 total focused checks).

Task 5 adapter regression command:

```bash
/usr/bin/colcon --log-base log test \
  --build-base build --install-base install \
  --packages-select rm65_teleop_adapter --event-handlers console_direct+
/usr/bin/colcon test-result \
  --test-result-base build/rm65_teleop_adapter --all --verbose
```

Result: 100 reported test cases, 0 errors, 0 failures, 0 skipped. Focused
binaries reported quaternion math 17/17, orientation tracker 10/10,
AdapterLogic 31/31, AdapterConfig 9/9 and input deadman 6/6. Motion-profile
pytest reported 10/10. These counts are copied from command output rather than
estimated.

## Synthetic dry-run evidence

With `ROS_DOMAIN_ID=142`, `ROS_LOCALHOST_ONLY=1`, only the adapter and
synthetic probe were run. The probe verified first press without orientation
jump, Quest +X rotation mapping to RM -Y, simultaneous translation and rotation,
finite/normalized/continuous quaternion output, release freeze, fresh
Quest/robot anchors on repress, and a jump-free repress first frame.

Result: `synthetic dry-run verified`; preview count 121, status count 11,
hardware command publisher count 0, and adapter process count after cleanup 0.
This is software dry-run evidence only.

## Preserved translation and command path

The Quest bridge production files and all three motion-profile YAML files are
unchanged. Translation mapping, scaling, velocity/step/anchor limits, workspace,
deadman thresholds, watchdogs, follow/control timing, stop behavior and
`stop_repeat_count` retain their existing semantics. The adapter remains the
only possible publisher to `/right/rm_driver/movep_canfd_cmd`, and dry-run
creates no publisher for that topic.

## Live Quest validation

Human-assisted live Quest dry-run was completed without RM driver or real robot
motion and accepted by the operator.

- `/q2r_right_hand_pose`: about 70.7–72.1 Hz
- raw quaternion norm range: 0.9999999753–1.0000000714
- maximum observed adjacent-sample angular change in the stillness window: 1.9324 deg
- invalid raw/preview quaternion samples: 0 across 50,064 raw and 43,413 preview samples
- first Grip ACTIVE orientation error: 0.0 deg
- release: `preview_after_release=0`
- repress first-frame orientation error: 0.0 deg
- naturally observed q/-q sign flips: 202; minimum raw dot -0.9999999993
- sign flips produced no preview jump and no orientation-jump fault
- two principal live wrist-rotation traces produced expected-preview orientation
  error of 0.0 deg; one additional 2.037 deg re-anchor stability sample also matched
- no orientation fault occurred; two existing `input_not_fresh` watchdog events
  safely entered `REARM_REQUIRED`
- hardware command publisher count remained 0 and RM driver was not started

The originally planned third independent 10–20 deg live rotation was explicitly
waived by the human operator after two accepted rounds; no substitute data is
claimed for that omitted action.

## Real RM65 qualitative validation

After the live Quest gate passed, the operator performed a real right-RM65
orientation smoke test. The first hardware trial used a temporary conservative
orientation envelope. After the operator reported the motion felt correct, the
temporary override was removed and the approved V1 values were restored:

- `rotation_scale=1.0`
- `max_angular_velocity_rad_s=1.5707963267948966` (90 deg/s)
- `max_angular_step_rad=0.01`
- `max_anchor_angle_rad=1.5707963267948966` (90 deg)

The operator reported the restored V1 response was substantially more responsive
and acceptable for continued development. This is a qualitative field acceptance,
not a quantitative tracking/safety characterization: no complete per-axis table of
commanded-vs-feedback angle, overshoot, stopping distance, long-duration jitter, or
repeatability was recorded in this session.

## Remaining validation

- quantitative real-RM65 orientation tracking error by axis
- overshoot, stopping distance, long-duration stillness/jitter and repeatability
- systematic combined-rotation and simultaneous translation+rotation measurements
- longer-duration watchdog/network robustness and workspace/collision safety

## Checkpoint commits

1. Task 1 quaternion math: `426420d81270d1ea545f2f537adf11ac21268064`
2. Task 2 orientation tracker: `b41f3142c6a1f284ba82c3f1af4b98bb8383b7cd`
3. Task 3 anchored AdapterLogic: `bdb0da0c5b2fffffdde77d2daba0e0959220cb8e`
4. Task 4 safety envelope: `a4a04a72737716ef26ede463f0aaa52d9e8721ed`
5. Task 5 node/config/dry-run: `c8aba4a146248416d446e8b3cc763ca4abb3f950`
