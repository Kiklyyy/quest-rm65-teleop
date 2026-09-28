# Right LinkerHand L7 Quest index toggle

## Baseline and scope

- Branch: `feat/right-linkerhand-quest`, based on `feat/left-rm65-teleop` SHA `57e919fe57818865b179be0d4ac2b57e0714fb9e`.
- Independent `/right_linkerhand` Python node in `rm65_teleop_adapter`; right/left arm adapter, Grip, Home, Quest message and `/home/lh/robot` are unchanged.
- The onsite SDK `O7_JOINT_KEYS` order was checked: `Thumb_Pitch, Thumb_Yaw, Index_Pitch, Middle_Pitch, Ring_Pitch, Little_Pitch, Thumb_Roll`.

## Interface and behavior

- Subscribe: `/q2r_right_hand_inputs` (`quest2ros/msg/OVR2ROSInputs`), field `press_index` only.
- `press_index >= 0.60` is PRESSED; `<= 0.40` is RELEASED; the band retains the previous semantic state. Each armed RELEASED → PRESSED edge toggles once. Holding or releasing the trigger causes no hand command.
- Startup logical state is `OPEN`, first press is armed, and `target=null`. Hardware startup reads `get_state()` and `get_fault()` before accepting input; it never sends an automatic OPEN command.
- First press sends CLOSED `[73,0,0,0,0,0,156]`; second sends OPEN `[73,0,255,255,255,255,156]`; subsequent presses alternate. These are canonical raw SDK joint targets from the onsite GUI.
- Stale inputs hold the last commanded position and disarm toggle. On reconnect, a valid RELEASED sample is required before the next press can toggle. NaN/Inf behaves the same way, increments the diagnostic counter, and never commands OPEN.
- Publish: `/right/linkerhand/status` (`std_msgs/msg/String` JSON): ROS `stamp`, `trigger_value`, `trigger_pressed`, `trigger_armed`, `hand_toggle_state` (`OPEN`/`CLOSED`), `target`, `actual`, `fault_codes`, `communication_ok`, `input_fresh`, `dry_run`, `state`, `error`, `invalid_input_count`. `target=null` before first command; dry-run has null actual/faults and `communication_ok=false`.
- `start_linkerhand:=false` is the right launch default. Explicit `true` with `mode:=dry_run` does not import/connect SDK. Explicit `true` with `mode:=hardware` uses `LinkerHandApi(hand_type="right", hand_joint="L7", modbus="RML")` from `/home/lh/quest2ros2_ws/linkerhand/linker_hand_python_sdk`. It retains the onsite RealMan API2 tool-RS485 transport and reads position/faults. The SDK itself is not modified or copied. Fault/communication gating and warning throttling remain; force/current are not used.

## Software verification

- Run `/usr/bin/colcon build --symlink-install --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter` from this worktree after sourcing ROS, `/home/lh/robot/install`, and this worktree.
- Run isolated tests with `ROS_DOMAIN_ID=143`, `ROS_LOCALHOST_ONLY=1`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`: logic tests, ROS node tests with fake SDK and synthetic Quest Inputs, launch tests, and adapter regression.
- Build: four packages passed (`quest2ros`, `ros_tcp_endpoint`, `q2r2_bringup`, `rm65_teleop_adapter`). Isolated adapter regression: 17/17 CTest entries and 177/177 reported tests, zero failures/skips. Within these, toggle logic 9/9, ROS node 8/8, launch contract 2/2. Grip, Home, and left adapter regression tests passed.
- An isolated real `ros2 launch` dry-run smoke checked explicit hand off/on: off had no hand node/status; on started `/right_linkerhand` and published startup `target=null`, first press CLOSED, release held CLOSED, second press OPEN. No right RM65 movep publisher appeared. Both launch groups were stopped afterward. No domain-42 input or live robot command was part of this checkpoint.

## Launch

```bash
conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /home/lh/robot/install/setup.bash
source /home/lh/quest2ros2_ws/.worktrees/right-linkerhand-quest/install/setup.bash
export ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1
ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py \
  mode:=dry_run start_linkerhand:=true start_tcp:=false \
  start_bridge:=false start_status:=false use_rviz:=false
```

## Hardware evidence and next step

- The operator reports that the onsite SDK connection, real feedback, and open/close direction have already been manually validated. This software change has **not** been tested against the real hand.
- The operator later completed a right-side A/B hardware comparison: `start_linkerhand:=false` made every observed right Grip re-anchor normally, without an old-position jump; `start_linkerhand:=true` made the right arm jump toward an old position on Grip press after the SDK connected. This is a confirmed correlation, not yet an identified API call or controller-state root cause. Dual-arm availability and cross-control isolation remain unverified. No Home or knife task was tested.
- Quest/TCP dropouts remain an open issue; arm watchdog and hand input timeout are unchanged. Grasp force and knife handling are unverified.

## Right RM driver / LinkerHand coexistence diagnosis

The right adapter's existing `ARMED → ACTIVE` logic captures the latest UDP robot pose as `robot_anchor`, assigns `last_command=robot_anchor`, and emits that as its first command. `test_adapter_logic.cpp` already checks this for initial press and repress. A new `first_command_anchor` log records the live anchor, first outgoing TCP pose/quaternion, and translation difference at every Grip activation without changing the command algorithm.

The actual onsite SDK constructor path is:

1. `LinkerHandApi(right,L7,RML)` loads `setting.yaml`, resolves `realman://169.254.128.19:8080` (tool Modbus port 1, 115200 baud, timeout 3, voltage 3), and creates `LinkerHandL7RS485`.
2. `RealmanModbusClient` creates `RealmanArmClient(auto_connect=True)`; its API2 layer creates `RoboticArm(RM_TRIPLE_MODE_E)` and calls `rm_create_robot_arm(169.254.128.19,8080)` on a **second** controller connection.
3. It calls `rm_set_tool_voltage(3)` and `rm_set_modbus_mode(1,115200,3)`.
4. The hand constructor reads L7 version through `rm_read_multiple_input_registers` (input registers 153–158); serial number is a local placeholder for this L7 implementation.
5. The ROS node immediately reads position registers 0–6 and fault registers 28–34, then continues feedback polling. A later `finger_move` writes seven holding registers starting at 0 through `rm_write_registers`. Shutdown invokes `rm_delete_robot_arm` on that second connection.

No explicit arm `movej`, `movep`, `move_stop`, follow, trajectory-mode, CANFD-mode, UDP-setting, or pose-setting call appears in this SDK constructor/write path. The controller's internal effects of second connection, tool voltage, or Modbus configuration remain unknown until staged hardware observations.

By comparison, `/home/lh/robot` `rm_driver` (read only) calls `rm_init(RM_TRIPLE_MODE_E)`, `rm_create_robot_arm`, and `rm_set_realtime_push` for UDP feedback. Its `trajectory_mode=0` and `radio=0` are local parameters passed with each `rm_movep_canfd`; `follow` comes from the command message. It does not separately set these motion modes at startup. Existing driver Modbus topics could in principle reuse its handle, but the three-generation `Write_Modbus_RTU_Registers_Callback` allocates `int hold_mul_data[10]` and copies `2 × num` byte values into it. An L7 seven-register write would copy 14 values, exceeding that buffer. The current driver topic is therefore not a safe unmodified Option B for L7 bulk writes, and `/home/lh/robot` was not edited.

The currently available API2 tool-register methods require a connected `RoboticArm` handle; no verified tool-only connection path was found, so merely replacing the high-level wrapper with a smaller wrapper would still create a second controller connection. Reusing the installed driver's write topic is blocked by the buffer issue above. Restoring controller modes after SDK initialization would be speculative without B/C state evidence and is not implemented.

`right_linkerhand_node` now accepts `connect_only:=true` in hardware mode, or `linkerhand_connect_only:=true` through the right launch. It still constructs the onsite SDK and polls `get_state/get_fault`, but ignores Quest input and never calls `finger_move`; status reports `CONNECT_ONLY`, `target=null`, and `connect_only=true`. For the first coexistence stage, start this executable **alone**, without a teleop adapter or Quest motion:

```bash
ros2 run rm65_teleop_adapter right_linkerhand_node --ros-args \
  -p dry_run:=false -p hardware_write_enabled:=true -p connect_only:=true
```

Before any hardware stage, the onsite operator must confirm a stationary right arm, clear path, and reachable stop. Capture an A/B/C comparison with the existing right driver as the sole arm controller client plus the optional SDK: A driver only; B driver + `connect_only`; C after exactly one hand write. In each stage record `/right/rm_driver/udp_arm_position` and `/right/joint_states` freshness/pose, `/right/linkerhand/status` communication/faults, driver `trajectory_mode`/`radio` parameters, `/right/rm_driver/get_realtime_push_result` if queried through the driver's existing connection, controller errors, and physical motion. Tool voltage, tool RS485 mode, and internal CANFD planner state lack a confirmed read-only path on this installed three-generation driver; mark them unavailable rather than opening another API2 client merely to inspect them.

| Field | A: driver only | B: SDK connect-only | C: after hand write |
|---|---|---|---|
| TCP/joint feedback freshness and physical stationary state | pending onsite | pending onsite | pending onsite |
| Controller UDP configuration and error | pending onsite | pending onsite | pending onsite |
| Tool voltage / RS485 / internal planner mode | readback path unconfirmed | readback path unconfirmed | readback path unconfirmed |
| Hand feedback/faults | no hand node | pending onsite | pending onsite |

The operator was unavailable for this software diagnostic checkpoint. No new controller connection, hand write, Grip test, Home action, or left-arm session was started. Connect-only and backend-call-sequence tests establish software behavior; they cannot establish physical coexistence or the exact conflicting controller state. Do not apply a guessed follow/trajectory-mode reset. If B reproduces the jump, bisect connection vs voltage vs Modbus configuration with operator-supervised single-variable probes; if only C reproduces it, inspect the register-write path and controller trace. Repeat the original Grip A/B after a fix before claiming no-jump PASS.

Software result for this checkpoint: four affected packages built in independent `/tmp/right-linkerhand-coexistence-{build,install,log}` paths, without replacing the original worktree install. Isolated domain 143 adapter regression passed 18/18 CTest entries and 183/183 reported tests (0 errors/failures/skips): LinkerHand logic 9/9, ROS node 10/10, launch contract 2/2, onsite SDK transport/constructor mock 3/3, plus unchanged Grip/Home and left adapter regressions. The existing off/on real-launch dry-run smoke also passed in domain 143 with no RM movep publisher. A user-owned hardware launch parent PID 286650 was found during this work, with no domain-42 nodes, driver/hand children, or TCP 10000 listener at the inspection time; it was left untouched at the user's explicit request.
