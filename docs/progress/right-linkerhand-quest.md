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
- The operator deferred the requested dual RM65 + right LinkerHand integration session until later. RM driver/SDK coexistence, simultaneous availability, and cross-control isolation remain unverified. No Home or knife task is included in that session.
- Quest/TCP dropouts remain an open issue; arm watchdog and hand input timeout are unchanged. Grasp force and knife handling are unverified.
