# Right-arm Home and stability progress

## Scope and isolation

- Branch: `feat/recenter-home`.
- Ubuntu worktree: `/home/lh/quest2ros2_ws/.worktrees/recenter-home`.
- Base: current `origin/main` at `0247970097e4fb86c5be443e6a5b3d43c745502e`.
- Only the right-arm adapter and its interfaces were changed. `/home/lh/robot` was sourced for interfaces and was not edited. At the initial software checkpoint, no RM driver, real Home goal, left arm, or gripper operation was started. The later real-arm results are recorded chronologically below.
- **Current closeout: right RM65 Home execution and mid-motion B-release cancel hardware validated.** Quest/TCP input stability remains open. Earlier pending statements below describe their respective checkpoints, before the subsequent hardware tests.

## Confirmed controls and configuration

- Physical A -> `button_lower`; reserved without new motion behavior. Physical B -> `button_upper`; selected by `home_button_field: upper`.
- Source: operator-confirmed Quest2ROS2 mapping; A was the former pre-trigger deadman button. No new A/B probe was performed.
- Grip `press_middle` remains the teleop deadman (`>=0.60` pressed, `<=0.40` released). Released -> Grip pressed still captures fresh Quest and RM anchors.
- Configured Home joint names: `joint1`, `joint2`, `joint3`, `joint4`, `joint5`, `joint6`. Incoming JointState positions are reordered by these names, with missing/duplicate/non-finite/mismatched samples rejected.
- Operator-confirmed 2026-09-24 Home target in degrees: `[68.3241063822369, -8.489398369548377, 60.14265142722264, 31.52005176840807, 51.634258495569824, -144.10081659391062]`. The old temporary target `[-95.605, 4.406, -80.034, -22.695, -48.462, 97.570]` is retired. Hold: `1.5 s`. Nominal speed: `15 deg/s`. Duration is the farthest joint angular distance divided by speed, with a minimum that only slows the move.
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
- A later read-only status sample still showed `ARMED`, both command paths ready, and `home_action_state=IDLE`, but `rearm_count=11` and `watchdog_count=11` since the adapter restart. The sampled inputs were fresh at that instant. No Home or Grip activation was initiated by this task. The counters are consistent with recurring input-freshness interruptions and require investigation before a motion test.
- No Home goal was sent. No real Home motion was performed. real RM65 Home validation remains pending.


## 2026-09-24 operator-confirmed current posture as new Home

- The initial fresh read-only samples were stable but differed materially from the previous preflight display `[68.324, -6.424, 84.067, 40.032, 36.801, -139.886]` deg. Work stopped before editing until the onsite operator explicitly confirmed that the **newer current right-arm posture** was the intended default Home. A further fresh `/right/joint_states` frame at stamp `1790247560.584515341` remained consistent with those samples. Its six names were unique and matched `joint1` through `joint6`; every position was finite. Positions were matched by name and converted from radians to degrees, rather than assuming array order or copying the three-decimal report.

| Joint | Fresh rad | New Home deg | Difference from previous displayed preflight deg |
|---|---:|---:|---:|
| joint1 | 1.1924806148529052 | 68.3241063822369 | +0.000106382 |
| joint2 | -0.1481679530620575 | -8.489398369548377 | -2.065398370 |
| joint3 | 1.0496872882843018 | 60.14265142722264 | -23.924348573 |
| joint4 | 0.550128683757782 | 31.52005176840807 | -8.511948232 |
| joint5 | 0.9011878175735474 | 51.634258495569824 | +14.833258496 |
| joint6 | -2.5150337043762208 | -144.10081659391062 | -4.214816594 |

- `docs/INTERFACE.md` was updated before the implementation configuration. Only `home_joint_degrees` changed in `hardware.yaml`; joint names, hold time, speed, action, deadman, B binding, motion profiles, mapping, watchdogs, and workspace were kept. README and hard-coded test expectations were synchronized. The target remains a startup configuration parameter, not C++ code.
- The four-package worktree build and complete isolated regression used system Python and `/usr/bin/colcon` with Conda variables removed, `ROS_DOMAIN_ID=143`, `ROS_LOCALHOST_ONLY=1`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. Result: **206 tests, 0 errors, 0 failures, 0 skipped**. The suite includes joint-name reorder, degree-to-radian conversion, trajectory duration, B hold, cancel acknowledgment, `REARM_REQUIRED`, dry-run isolation, command-path ownership, and XYZ/orientation regressions.
- Before restart, read-only Inputs showed Grip `press_middle=0.0`, B `button_upper=false`, and A `button_lower=false`; status was `ARMED`, `home_action_state=IDLE`, and both command paths ready. The original launch did not exit on SIGINT; targeted SIGTERM stopped its launch/adapter, but three launch children remained orphaned. A first replacement launch could not bind Quest TCP port 10000 while the old endpoint remained, and reported `DISABLED` with missing Quest inputs. Those exact old child processes and the first replacement launch/children were stopped with targeted SIGTERM. The final launch from this worktree bound port 10000, Quest reconnected, and exactly one new adapter/TCP endpoint/target bridge/status monitor was observed. Right RM driver and right-only `rm_control` were not restarted; `/home/lh/robot` was not edited.
- After final restart, the adapter returned the configured Home parameter exactly. Read-only Inputs again showed Grip and B released. Sampled status: `state=ARMED`, `home_action_state=IDLE`, `command_path_ready=true`, `home_command_path_ready=true`, with fresh Quest/input/robot/joint data. The final direct JointState stamp was `1790248113.052258613`.

| Joint | Post-restart current deg | New Home deg | Home - current deg | Abs delta deg |
|---|---:|---:|---:|---:|
| joint1 | 68.327104169 | 68.324106382 | -0.002997786 | 0.002997786 |
| joint2 | -8.485399414 | -8.489398370 | -0.003998956 | 0.003998956 |
| joint3 | 60.140652903 | 60.142651427 | +0.001998524 | 0.001998524 |
| joint4 | 31.520051768 | 31.520051768 | 0.000000000 | 0.000000000 |
| joint5 | 51.642256407 | 51.634258496 | -0.007997911 | 0.007997911 |
| joint6 | -144.100816594 | -144.100816594 | 0.000000000 | 0.000000000 |

- Maximum absolute delta: **0.007997911 deg**. The current 15 deg/s formula with its 0.1 s minimum gives a **0.1 s nominal trajectory duration** from this sample; no trajectory was requested. A sampled `rearm_count=5`, `watchdog_count=5` after restart shows intermittent input freshness interruptions are still occurring and should be investigated before any real Home test.
- **Home goals sent: 0. Home motion performed: none.** New Home target configured; real Home motion/cancel validation still pending. The next gate is onsite review of input/watchdog stability and a separately authorized, controlled real Home motion/cancel test from a verified non-Home pose.


## 2026-09-24 read-only Home idle stability validation (STABILITY NO-GO)

- Branch and remote both started at `c94b499502626436bf770d1b4bb51fbeea945c07`; worktree was clean. No launch, TCP endpoint, adapter, RM driver, or `rm_control` was restarted. The live graph initially had one `/right/rm_driver`, one `/right/rm_control`, and one `/rm65_teleop_adapter`; the Action had one adapter client and one controller server. `movep` was adapter -> driver, `movej` was controller -> driver, and stop was adapter -> driver + controller, with no extra command endpoint. The same ownership/counts were observed after the timing run. Across 1,294 sampled adapter statuses, both command-path readiness flags stayed true.
- Before observation, direct `/q2r_right_hand_inputs` showed `press_middle=0.0`, `button_upper=false`, `button_lower=false`. A separate pair of pre-run statuses showed `ARMED`, fresh inputs/feedback and `watchdog_count=78`; no restart occurred between that check and the timed run. The first status in the timed run was at `2026-09-24 19:21:53.033 +08:00`: `ARMED`, `rearm_count=120`, `watchdog_count=120`, all five freshness flags true. The timed read-only subscriber ran from `19:21:50.560` to `19:24:05.580 +08:00`, **135.003 s** total; first-to-last status coverage was **132.452 s**. The last status was `ARMED`, `rearm_count=123`, `watchdog_count=123`, all freshness flags true. The increase from 78 before the run to 120 at its baseline is further evidence of intermittent events outside startup, but the three events below are the counted events within the timed window.
- The subscriber only received the five input/feedback topics and adapter status. It created no publishers. All 9,509 direct Inputs samples kept Grip, B, and A released. Maximum observed per-joint feedback range was 0.011 deg, consistent with a stationary arm at this scale.

| Topic | Approx. receive rate | Maximum receive gap | Threshold | Crossings |
|---|---:|---:|---:|---:|
| `/q2r_right_hand_pose` | 72.028 Hz | 342.907 ms | 200 ms | 3 |
| `/q2r_right_hand_inputs` | 72.027 Hz | 342.989 ms | 200 ms | 3 |
| `/quest_right_target_pose` | 50.044 Hz | 36.314 ms | 200 ms target timeout | 0 |
| `/right/rm_driver/udp_arm_position` | 197.588 Hz | 22.664 ms | 100 ms | 0 |
| `/right/joint_states` | 197.589 Hz | 22.698 ms | 100 ms | 0 |

- The adapter reported `ARMED` for 1,288 status samples and `REARM_REQUIRED` for six samples. All six `REARM_REQUIRED` samples had `reason=input_not_fresh` and both `quest_pose_fresh=false` and `inputs_fresh=false`; `target_fresh`, `robot_fresh`, and `joint_state_fresh` stayed true in every status sample. Maximum reported ages were Quest Pose 309.784 ms, Inputs 309.773 ms, robot 16.354 ms, and joints 16.414 ms. The direct target continued at about 50 Hz with a 36.314 ms maximum gap, so target publication alone did not establish live Quest input.

| Watchdog event (+1 each) | Previous -> new state | Reason | Pose / Inputs age at event | Direct Pose / Inputs gap on recovery | Robot / Joint age at event |
|---|---|---|---|---|---|
| 19:22:49.949 +08:00 | `ARMED` -> `REARM_REQUIRED` | `input_not_fresh` | 202.071 / 201.615 ms | 342.907 / 342.989 ms | 1.436 / 1.393 ms |
| 19:22:52.004 +08:00 | `ARMED` -> `REARM_REQUIRED` | `input_not_fresh` | 204.795 / 204.387 ms | 310.859 / 311.149 ms | 1.473 / 1.550 ms |
| 19:22:52.949 +08:00 | `ARMED` -> `REARM_REQUIRED` | `input_not_fresh` | 204.818 / 204.807 ms | 320.191 / 320.276 ms | 1.188 / 1.269 ms |

- Quest Pose and Inputs became stale together to within roughly 0.5 ms; there was no isolated Inputs-only dropout. The direct recovery gaps and the adapter's independent age/freshness measurements agree, while robot feedback and target publication continued. The read-only TCP log showed no connection/error/reconnect entry inside the 135 s window. A post-run socket snapshot showed established TCP connections from `192.168.5.45` to port 10000, owned by the single endpoint process; it showed two established sockets from that same peer, but this alone does not explain the paired data gaps or prove the Quest sender stayed continuously healthy. Further Quest/TCP receive-side timing evidence is needed to locate the stall within the shared input path.
- A later read-only status sample after the timed subscriber exited, without a restart, showed `ARMED`, `rearm_count=129`, and `watchdog_count=129`. These six additional increments were outside the instrumented 135 s window; their individual stale sources were not captured by that run.
- **Decision: STABILITY NO-GO.** These watchdogs recurred about 59-62 s into an already-running idle observation; they were not confined to launch/TCP reconnect startup. Existing `target_timeout=200 ms`, `quest_pose_timeout=200 ms`, `inputs_timeout=200 ms`, `robot_timeout=100 ms`, and `joint_state_timeout=100 ms` were not modified. No Home goal, `FollowJointTrajectory`, Cartesian motion, `movep`, `movej`, manual stop experiment, robot motion, or restart was initiated. Real Home motion/cancel validation remains pending. Next gate: instrument/read the Quest -> TCP endpoint delivery path, including the two observed connections and packet receive gaps, then repeat at least 120 s idle stability under the same limits before considering a separately authorized first real Home test.

## 2026-09-24 first real Home goal failure and trajectory compatibility fix

- After the earlier read-only stability run, the onsite operator moved the right arm away from Home and held B. The adapter reached `HOMING`, but the arm did not move. The right-only `/right/rm_control` terminal printed `First Move_group give us 1 points` and then `[ros2run]: Segmentation fault`. The adapter remained in `HOMING` without an Action terminal result. These are operator-reported live observations; no second real Home goal was sent during this fix.
- The old adapter sent one point with six `positions` and `time_from_start`, leaving `velocities` and `accelerations` empty. The available [RealMan ROS2 Humble `rm_control.cpp`](https://github.com/RealManRobot/ros2_rm_robot/blob/humble/rm_control/src/rm_control.cpp) accepts that Action goal, then for 1-3 points indexes `positions[0..5]`, `velocities[0..5]`, and `accelerations[0..5]` without length checks. Its >3-point branch uses a cubic spline with zero endpoint velocities and a 20 ms output timer. This explains the observed crash path. The onsite `/home/lh/robot` copy was not accessible in this work environment, so its exact current contents could not be rechecked.
- The adapter now builds four points at normalized times 0, 1/3, 2/3, and 1 from fresh current joints to the unchanged configured Home. Every point carries six finite positions, velocities, accelerations, and a time. The smoothstep positions reproduce the controller's zero-end-velocity cubic interpolation; duration is at least 1.5 times the farthest joint delta divided by `home_speed_deg_s` (minimum 0.1 s), accounting for the cubic's 1.5× peak slope. `home_speed_deg_s` remains 15.0 in hardware configuration. B, Grip, watchdog, mapping, and action endpoint behavior were not changed.
- This work environment had no ROS 2/colcon installation or access to the robot host. The requested adapter build and `test_home_trajectory`/`test_home_action_client` could not run here; no real-arm motion or repeat Home test was performed. The earlier idle stability NO-GO remains open. Before a controlled onsite retry, build this branch on the ROS host, run the two targeted tests, confirm the actual local `rm_control.cpp` matches the inspected Humble access path, and resolve the Quest/TCP freshness instability.


## 2026-09-24 RealMan Home cancel terminal compatibility fix

- The onsite operator reports that the four-point Home trajectory now works with real RM65 hardware, `rm_control` no longer segfaults, and multiple real Home goals succeeded. In a mid-motion B-release attempt, the controller logged `First Move_group give us 4 points`, `Second Move_group max_time is 5.733918`, then `Goal Succeeded` about 2.675 s after the goal began. These are operator-provided hardware observations; this software-only checkpoint did not repeat motion.
- The confirmed RealMan `rm_control.cpp` behavior is: `handle_cancel()` accepts cancellation; its execution loop checks `goal_handle->is_canceling()` only while `point_changed` remains true; the `/move_stop_cmd` callback clears `point_changed`; after the loop exits, the controller calls `goal_handle->succeed(...)`. Thus B release can send both Action cancel and physical stop, yet the vendor Action terminates with `SUCCEEDED` rather than `CANCELED`.
- `HomeActionClient` now snapshots `cancel_requested_` as `cancellation_was_requested` on entry to the terminal result callback, before clearing the flag. A terminal `SUCCEEDED` with `FollowJointTrajectory::Result::SUCCESSFUL` reports `HomeActionEvent::CANCELED` only when that local cancel request was pending. Ordinary success without a cancel request remains `SUCCEEDED`; actual `CANCELED` and abort handling are unchanged. The adapter still waits for the real Action terminal callback before leaving `HOMING`. No `/home/lh/robot` file was modified.
- Only `rm65_teleop_adapter` was built on the Ubuntu ROS host with system Python/colcon. Isolated `ROS_DOMAIN_ID=143`, `ROS_LOCALHOST_ONLY=1` targeted `test_home_action_client` passed: CTest 1/1 executable, GTest 8/8 cases, 0 failures/errors. The new case sends a goal, requests cancel, has the synthetic vendor return successful `SUCCEEDED`, and requires a `CANCELED` adapter event. The existing normal-success case ran and still required `SUCCEEDED`. The full regression was intentionally not run.
- No real Home goal, Cartesian command, manual stop, or robot motion was initiated by this checkpoint. One controlled approximately five-second real Home with B released during motion remains the final onsite compatibility check: verify physical stop and final adapter `CANCELED`/`REARM_REQUIRED` before closing this phase. This is still pending and must not be described as validated by the targeted test.


## Right Home hardware closeout (operator-confirmed)

- The formal Home target remains `[68.3241063822369, -8.489398369548377, 60.14265142722264, 31.52005176840807, 51.634258495569824, -144.10081659391062]` degrees in joint1–joint6 order. The old temporary target is retired.
- The initial one-point trajectory logged `First Move_group give us 1 points` and crashed `rm_control`. After the four-point trajectory fix, multiple real goals logged `First Move_group give us 4 points` and `Goal Succeeded`, including returns from clearly away-from-Home postures lasting about 5–7 seconds. This is real motion validation, not an already-at-Home success.
- The onsite operator then performed the final mid-motion B-release test. The arm physically stopped. RealMan can emit terminal `SUCCEEDED/SUCCESSFUL` after stop clears its internal `point_changed`; the adapter's locally pending cancel compatibility rule reports `HomeActionEvent::CANCELED` only in that case. The final sampled status was `state=ARMED`, `deadman_pressed=false`, `home_button_pressed=false`, `home_hold_progress=0`, `home_action_state=CANCELED`, `command_path_ready=true`, `home_command_path_ready=true`, `reason=""`. `ARMED` is the expected state after `HOMING → REARM_REQUIRED → released B and Grip with fresh input → ARMED`; the adapter did not re-enter `ACTIVE`.
- Ubuntu `rm65_teleop_adapter` build and targeted `test_home_action_client` passed after the compatibility fix (CTest 1/1, GTest 8/8). The full earlier regression after the new target was 206 tests, 0 errors/failures/skips. This documentation checkpoint performed no new hardware motion or test run.
- **Closed:** right Home execution, B-release physical stop/cancel, and pending-local-cancel/vendor-success compatibility are hardware validated. **Open, separate issue:** Quest pose and inputs can simultaneously gap beyond 200 ms (previous observed maximum about 343 ms), raising watchdog/rearm counters. Do not treat this Home closeout as a Quest/TCP stability fix.
