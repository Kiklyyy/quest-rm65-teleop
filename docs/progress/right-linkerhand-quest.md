# Right LinkerHand L7 Quest index control

## Scope and Git baseline

- Development branch: `feat/right-linkerhand-quest`, independent Ubuntu worktree `/home/lh/quest2ros2_ws/.worktrees/right-linkerhand-quest`.
- Base read from `feat/left-rm65-teleop` at `57e919fe57818865b179be0d4ac2b57e0714fb9e` on 2026-09-28. The source left worktree had existing edits to `hardware.yaml` and `left_hardware.yaml`; these were neither copied nor changed.
- A separate dirty `feat/right-linkerhand` worktree already existed and was left untouched. `/home/lh/robot` was only sourced/read, never edited.

## Design and onsite SDK facts

- The independent `/right_linkerhand` Python process is installed by `rm65_teleop_adapter`; no arm adapter C++ state, Home, Grip, Quest message, driver, or hardware YAML is changed.
- Subscribes to `/q2r_right_hand_inputs` (`quest2ros/msg/OVR2ROSInputs`), using only `press_index`. Open `[255,0,255,255,255,255,255]` at 0.0 and closed `[0,0,0,0,0,0,255]` at 1.0 are linearly interpolated per axis. Finite out-of-range input is clamped; NaN/Inf maps to open with a diagnostic count and warning. Fixed axes 1 and 6 remain 0 and 255.
- The onsite `O7_JOINT_KEYS` order is `Thumb_Pitch, Thumb_Yaw, Index_Pitch, Middle_Pitch, Ring_Pitch, Little_Pitch, Thumb_Roll`. The GUI reference poses are used verbatim; the SDK's `L7_positions.yaml` right-open preset has a different yaw value and is not used.
- Hardware mode imports `/home/lh/quest2ros2_ws/linkerhand/linker_hand_python_sdk` and calls `LinkerHandApi(hand_type="right", hand_joint="L7", modbus="RML")`. The explicit RML transport prevents a fallback to CAN. This onsite SDK contains uncommitted RealMan API2 tool-RS485 adaptation, including `realman_modbus.py`; it is not copied into this repository. SDK initialization configures tool voltage and Modbus mode through the right RM65 controller. The SDK process owns the hand connection and closes it on shutdown.
- `right_quest_teleop.launch.py` defaults `start_linkerhand:=false`. With `true`, `mode:=dry_run` maps input and reports status without importing SDK or touching hardware; `mode:=hardware` connects SDK and may write. Invalid dry-run/write gate combinations are rejected. A 20 Hz timer writes changed targets only while input is fresh and initial fault/feedback is available. Feedback and raw fault codes are read separately at 2 Hz. Stale input suspends writes; fault codes or a communication failure also suspend writes. No force/current control is used.
- `/right/linkerhand/status` is `std_msgs/msg/String` JSON with ROS `stamp`, seven-axis `target` and `actual`, seven raw `fault_codes`, `communication_ok`, `input_fresh`, `dry_run`, `state`, `error`, and `invalid_input_count`. In dry-run, `actual` and fault codes are null and `communication_ok=false` because no SDK is connected. Target is null before the first Quest input. `INPUT_STALE` means no new write while the latest input is old; it is not an arm Home/deadman state.

## Software verification

- Mapping tests were run RED before implementation (missing module, 9 expected failures), then GREEN (9/9). Node tests used real ROS messages on isolated `ROS_DOMAIN_ID=143`, localhost-only, with in-memory SDK stand-ins; launch tests checked the default-off gate and mode mapping.
- A fault-before-first-write test found an initial-write gap. The node now reads feedback and fault codes before it can write, and blocks writes while fault/communication state is unknown or unhealthy.
- Four ROS packages (`quest2ros`, `ros_tcp_endpoint`, `q2r2_bringup`, `rm65_teleop_adapter`) built with `/usr/bin/colcon build --symlink-install --packages-select ...` and system Python 3.10 in this independent worktree. An incremental adapter build after the fault guard passed. `colcon test --packages-select rm65_teleop_adapter` with `ROS_DOMAIN_ID=143`, `ROS_LOCALHOST_ONLY=1`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` passed all 17 CTest entries. `colcon test-result --test-result-base build --all --verbose` reported **175 tests, 0 errors, 0 failures, 0 skipped** (including CTest wrapper records). The new mapping tests were 9/9, ROS node tests 6/6, and launch contract tests 2/2; the rest include right Home/Grip/orientation and left adapter regressions.
- A real `ros2 launch rm65_teleop_adapter right_quest_teleop.launch.py` smoke used only `mode:=dry_run`, `start_tcp:=false`, `start_bridge:=false`, `start_status:=false`, `use_rviz:=false`, and isolated domain 143. With `start_linkerhand:=false`, no hand node or hand-status publisher appeared. With `start_linkerhand:=true`, the hand node appeared and a synthetic `press_index=0.5` produced status target `[128,0,128,128,128,128,255]`, `dry_run=true`, `actual=null`; both cases had zero publishers on `/right/rm_driver/movep_canfd_cmd`. Both launch process groups were terminated by their exact PIDs after observation, and the isolated node graph was empty afterward.
- No SDK object was instantiated in any test that ran the launch. No LinkerHand hardware command, real grasp, knife test, RM65 motion, or domain-42 synthetic input was performed.

## Launch for a software preview

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

For a real Quest source, the normal right launch may supply TCP and bridge. Only after onsite single-owner and clearance checks should an operator use `mode:=hardware start_linkerhand:=true`; this was **not** run in this task.

## Remaining validation

- Confirm onsite SDK and RealMan API2 can share the right controller session with the existing RM65 driver without resource contention.
- Under onsite supervision, check open/mid/close direction and actual positions on the real right L7 with a clear, unloaded hand. Record response, fault codes, and stop behavior before any object handling. Do not infer knife handling or force-limited grasp from the software tests.
- Known Quest/TCP synchronous dropouts remain open. The hand node's stale-input behavior holds the last target; a resumed fresh input resumes mapping. This does not solve network stability.
