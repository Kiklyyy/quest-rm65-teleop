# Right-arm Home and stability progress

## Scope and isolation

- Branch: `feat/recenter-home`.
- Ubuntu worktree: `/home/lh/quest2ros2_ws/.worktrees/recenter-home`.
- Base: current `origin/main` at `0247970097e4fb86c5be443e6a5b3d43c745502e`.
- Only the right-arm adapter and its interfaces were changed. `/home/lh/robot` was sourced for interfaces and was not edited. No RM driver, real Home goal, left arm, or gripper operation was started.
- **real RM65 Home validation = pending.**

## Confirmed controls and configuration

- Physical A -> `button_lower`; reserved without new motion behavior. Physical B -> `button_upper`; selected by `home_button_field: upper`.
- Source: operator-confirmed Quest2ROS2 mapping; A was the former pre-trigger deadman button. No new A/B probe was performed.
- Grip `press_middle` remains the teleop deadman (`>=0.60` pressed, `<=0.40` released). Released -> Grip pressed still captures fresh Quest and RM anchors.
- Configured Home joint names: `joint1`, `joint2`, `joint3`, `joint4`, `joint5`, `joint6`. Incoming JointState positions are reordered by these names, with missing/duplicate/non-finite/mismatched samples rejected.
- Temporary Home target in degrees: `[-95.605, 4.406, -80.034, -22.695, -48.462, 97.570]`. Hold: `1.5 s`. Nominal speed: `15 deg/s`. Duration is the farthest joint angular distance divided by speed, with a minimum that only slows the move.
- Hardware action: `/right/rm_group_controller/follow_joint_trajectory` (`control_msgs/action/FollowJointTrajectory`). Hardware Home is enabled in `hardware.yaml`; dry-run Home is disabled and creates no real Home action client.

## State and safety behavior

- `ARMED` + released Grip + continuous B hold + fresh and valid inputs/joints + ready action + exclusive command/stop path enters `HOMING` once.
- `HOMING` emits no Cartesian `/right/rm_driver/movep_canfd_cmd`. B release, stale/invalid feedback, control-period loss, or command-path loss requests cancel+stop once. The adapter remains `HOMING` until an action terminal result.
- Success or confirmed cancellation enters `REARM_REQUIRED`; B must be released and Grip must complete release -> press before teleop can become `ACTIVE`. A and Grip cannot command Cartesian motion during Home. Rejection/abort enters `FAULT` and sends stop.
- On process shutdown during Home, cancel and stop are sent while ROS communication remains active, with a bounded wait for action completion.

## Test-driven checkpoints

| Task | RED evidence | GREEN regression result | Commit |
|---|---|---|---|
| 1 button binding | Missing face-button header failed compile | 103 tests, 0 failures | `43af410179d510ac3e3ae6b6952b82f12cf4f532` |
| 2 trajectory | Missing trajectory header failed compile | 108 tests, 0 failures | `00563ff57f02f94d4f010961d550e51ddb731ae7` |
| 3 state arbitration | Missing HOMING fields failed compile | 116 tests, 0 failures | `317af4ee9caa408a4edccd2a79903e76859d4858` |
| 4 action transport | Missing action-client header failed compile | 124 tests, 0 failures | `a891d532846fb923e6a7e871e8fc2b809826ec96` |
| 5 node integration | Missing Home-config header failed compile | 127 tests, 0 failures | `91d97eb39137caaeb5eefa1ffad5fdefd1e77cfa` |
| 6 diagnostics | New status tests failed 3 cases | 130 tests, 0 failures | `8ddb6572e7800198e4966ef834177dc38761afa5` |
| 7 synthetic/review/docs | Integration and review tests reproduced rearm, invalid-feedback, exclusive-path, control-period, invalid-joint diagnostic, and shutdown stop gaps | 203 tests, 0 errors/failures/skips | Final Task 7 commit |

The complete four-package build and test used `/usr/bin/colcon` and system `/usr/bin/python3`, with Conda deactivated. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` was set because incompatible user-site pytest plugins initially interrupted unrelated package tests. The final `/usr/bin/colcon test-result --test-result-base build --all --verbose` reported **203 tests, 0 errors, 0 failures, 0 skipped**.

## Isolated synthetic result

With `ROS_DOMAIN_ID=143` and `ROS_LOCALHOST_ONLY=1`, a local action server and test-only `/test/home/*` topics exercised:

1. B held less than 1.5 s: no goal; full hold: one goal with six ordered joint names, exact configured radian targets, and a duration that keeps every nominal average joint speed at or below 15 deg/s.
2. Quest movement and Grip press during `HOMING`: no Cartesian hardware command.
3. B release: cancel+stop, with `HOMING` retained before terminal `CANCELED`; then `REARM_REQUIRED`.
4. B released and re-held: a second goal succeeded; `REARM_REQUIRED`, with no retrigger while B stayed held.
5. Stale Quest pose: cancel+stop; restored input did not automatically resume teleop.
6. Invalid/duplicate joint feedback: cancel+stop and the distinct `home_joint_state_invalid` reason.
7. Process shutdown during Home: cancel+stop reached the synthetic endpoints before exit.

Observed aggregate: **5 test-only goals, 4 cancels, 1 success, 0 Cartesian commands, 0 publishers on the real Cartesian command topic**. The adapter subprocess exited and the test action server was destroyed. A separate dry-run node graph check found no real Home action client and no real Cartesian command publisher. Status input ages and the watchdog counter were also checked in the synthetic run. No real RM65 driver or motion was involved.

## Whole-branch review

Reviewed `main...feat/recenter-home` and the isolated Home diff against current `origin/main`. Local `main` is older than `origin/main`, so the latter is the precise Home implementation baseline. Review covered cancel acknowledgment, continuous-B retrigger, action callback ordering, joint reorder, watchdog cancellation, shutdown delivery, dry-run action isolation, single Cartesian publisher, translation/orientation/deadman regressions, quaternion sign handling, and command-path readiness.

RED -> GREEN fixes during Task 7 addressed: a post-Home B/Grip rearm race; missing invalid Quest/robot pose cancellation; missing command-path and control-period gates during Home; incorrect classification of invalid joints as stale; missing stop on reject/abort; and shutdown stop delivery. No unresolved Critical or Important issue was identified in this software/synthetic review. Real-arm Home and mid-motion B-release stop remain unvalidated pending operator testing.

## 2026-09-24 real-hardware Home preflight (NO-GO at Gate 2)

- Git: `git fetch origin` succeeded. Worktree `feat/recenter-home` was clean; HEAD and `origin/feat/recenter-home` were both `65c856b12381288fe7618c1ba27291705d1fd1c5` before this documentation checkpoint.
- Gate 0 process check: one right-only RM65 driver chain was observed (a `ros2 run` wrapper and its driver process), using `/right`, `169.254.128.19:8080`, and UDP `169.254.128.100:8090`. One `rm65_teleop_adapter_node` was running from this `recenter-home` worktree, launched with `mode:=hardware`, `motion_profile:=safe`, `start_rm_driver:=false`, and `use_rviz:=false`. No `competition_system`, CuRobo, or second RM driver matched the process check. The ROS node list included `/right/rm_driver` and `/rm65_teleop_adapter`, with no second adapter node observed.
- Gate 1 read-only samples: `/q2r_right_hand_inputs` reported `press_middle: 0.0`, `button_upper: false`, and `button_lower: false`; a `/q2r_right_hand_pose` sample was received. Adapter status was `ARMED`, `deadman_pressed: false`, `home_button_pressed: false`, `home_hold_progress: 0.000`, and `command_path_ready: true`. It reported Quest pose, inputs, robot, and joint feedback as fresh. These are sampled status claims, not direct joint or end-effector readings.
- Gate 2: `ros2 action list -t` displayed `/right/rm_group_controller/follow_joint_trajectory [control_msgs/action/FollowJointTrajectory]`, but `ros2 action info` reported **1 client** (`/rm65_teleop_adapter`) and **0 servers**. Adapter status reported `home_action_state: SERVER_UNAVAILABLE`. No `rm_control` process matched the Gate 0 process check. The Action name alone did not establish an available server.
- Decision: **NO-GO**. No controller was started or guessed. Gates 3-6 were not run after the missing-server stop condition. Command-topic ownership, direct joint angles, direct end-effector pose, Home deltas, and nominal duration remain unverified. A documented and verified right-only controller startup and a live single Action server are prerequisites before resuming the remaining read-only gates.
- No Home goal was sent. No real Home motion was performed. real RM65 Home validation remains pending.

## 2026-09-24 right-only Home runtime graph fix and preflight

- Source check (read-only under `/home/lh/robot`): the right side of `rm_65_dual_control.launch.py` specifies `/right/rm_control`, `follow=false`, `arm_type=65`, Action `/right/rm_group_controller/follow_joint_trajectory`, movej `/right/rm_driver/movej_canfd_cmd`, and stop `/right/rm_driver/move_stop_cmd`. The `rm_control.cpp` source creates that Action server, movej publisher, and stop subscriber. The `rm_driver.cpp` source creates movej, movep, and stop subscribers. Its timer has no movej output before a goal changes `point_changed` from its initial false value.
- After confirming Grip `press_middle=0.0`, B `button_upper=false`, adapter `ARMED`, no `HOMING`, and nearly unchanged joint readings over two samples, only right-side `rm_control` was started with `ros2 run rm_control rm_control --ros-args -r __ns:=/right -r __node:=rm_control -p follow:=false -p arm_type:=65 -p action_name:=/right/rm_group_controller/follow_joint_trajectory -p movej_topic:=/right/rm_driver/movej_canfd_cmd -p stop_topic:=/right/rm_driver/move_stop_cmd`. No dual launch, left arm, or second RM driver was started.
- Before the adapter fix, the live graph showed Action **1 client** (`/rm65_teleop_adapter`) and **1 server** (`/right/rm_control`); movep **1 publisher** (`/rm65_teleop_adapter`) and **1 subscriber** (`/right/rm_driver`); movej **1 publisher** (`/right/rm_control`) and **1 subscriber** (`/right/rm_driver`); stop **1 publisher** (`/rm65_teleop_adapter`) and **2 subscribers** (`/right/rm_driver`, `/right/rm_control`). The old adapter reported `command_path_ready=false`, reproducing the stop-count integration bug. One sampled status was `REARM_REQUIRED` due to a transient stale Quest input, unrelated to endpoint ownership. No B hold or Home goal was attempted.
- Fix: `command_path_ready` now checks the exact Cartesian publisher/subscriber identities and an allowed stop subscriber set. New `home_command_path_ready` additionally requires the exact movej path, both expected stop subscribers, one `/right/rm_control` node, one controller Action status publisher, and an available Action server. Extra or duplicate endpoints fail closed. Adapter Home entry and in-progress Home both require this Home path; Cartesian teleop may still use the driver-only topology. The new `home_movej_topic` parameter defaults to `/right/rm_driver/movej_canfd_cmd`. `docs/INTERFACE.md` describes the contract.
- RED: an isolated adapter plus fake driver/controller with two expected stop subscribers failed the old `command_path_ready` assertion. GREEN: both Home synthetic tests passed, including driver-only Cartesian acceptance, complete Home topology acceptance, unknown movep/movej publisher rejection, unknown stop subscriber rejection, missing controller Home rejection, and duplicate controller rejection. State-machine tests also cover Home-path loss cancel+stop and Cartesian availability without Home. The four-package full regression reported **206 tests, 0 errors, 0 failures, 0 skipped**; all tests used isolated `ROS_DOMAIN_ID=143`, `ROS_LOCALHOST_ONLY=1`.
- The original adapter launch was stopped normally and restarted from this worktree using `mode:=hardware motion_profile:=safe start_rm_driver:=false use_rviz:=false`; the right RM driver was not restarted. After the fix, the same live endpoint identities/counts were observed. A sampled adapter status was `ARMED`, `deadman_pressed=false`, `home_button_pressed=false`, `home_action_state=IDLE`, `command_path_ready=true`, and `home_command_path_ready=true`; Quest, input, robot, and joint feedback were reported fresh. Direct Inputs showed Grip 0.0 and B false. The controller remains a right-only instance.
- Direct `/right/joint_states` contained exactly `joint1` through `joint6`, six finite radian positions, and no duplicate names. Positions were reordered by name before converting to degrees. Direct `/right/rm_driver/udp_arm_position` feedback was finite: position `(-0.060333, -0.302324, 0.499888)` m and quaternion `(x=-0.076969, y=0.795339, z=-0.600112, w=-0.037084)` with norm about 0.999999.

| Joint | Current (deg) | Home (deg) | Delta Home-current (deg) | Abs delta (deg) |
|---|---:|---:|---:|---:|
| joint1 | 68.324 | -95.605 | -163.929 | 163.929 |
| joint2 | -6.424 | 4.406 | 10.830 | 10.830 |
| joint3 | 84.067 | -80.034 | -164.101 | 164.101 |
| joint4 | 40.032 | -22.695 | -62.727 | 62.727 |
| joint5 | 36.801 | -48.462 | -85.263 | 85.263 |
| joint6 | -139.886 | 97.570 | 237.456 | 237.456 |

- Maximum raw joint delta: **237.456 deg on joint6**. Nominal synchronized duration at 15 deg/s: **15.830 s**. Joint1 and joint3 each require about 164 deg. This is a large, unvalidated first real Home movement; the current Home planner uses these raw joint targets, not a wrapped or shortened joint6 alternative. Joint limits, workspace clearance, and the proposed first short-motion/cancel envelope still require onsite review. **Next gate: NO-GO for a first Home goal on this evidence alone.**
- No Home goal was sent. No real Home motion was performed. real RM65 Home validation remains pending.
