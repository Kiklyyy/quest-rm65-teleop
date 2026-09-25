# Left RM65 Quest teleop: software and dry-run phase

## Scope and base

- Branch `feat/left-rm65-teleop`; independent worktree `/home/lh/quest2ros2_ws/.worktrees/left-rm65-teleop`.
- Based on right Home closeout `074e0fa3b7b727fd39c4a2818a22114efe6ec1f3`, because `origin/main` did not yet contain right Home. This dependency remains until review/merge.
- **Software/dry-run only.** No left RM65 driver, left `rm_control`, dual launch, real command, real Home goal, or robot motion was started. `/home/lh/robot` was read/sourced but not edited.
- Right XYZ, orientation, Grip deadman, Home success and Home B-release cancel were already hardware validated on the base branch. This refactor has automated right regression evidence, not a new right hardware test. Quest/TCP pose and inputs can still gap about 343 ms; input stability remains open.

## Shared architecture and interface

- One `rm65_teleop_adapter_node` executable uses the existing `AdapterLogic`, orientation/quaternion, Home trajectory and Home Action client. No second safety state machine was copied.
- Configured absolute identities `expected_adapter_node`, `expected_driver_node`, and `expected_control_node` replace hard-coded `/right` command-graph ownership. The adapter checks its own fully qualified name. Exact endpoint sets still gate movep, movej, stop and Home Action; unexpected or cross-arm endpoints fail closed.
- Existing right hardware/dry-run YAML explicitly preserve all right topics, frame, node identities, mapping and Home target. Left has a separate `left_dry_run.yaml` with its own topics, status, preview and clear-fault service. There is no left hardware profile in this phase.
- The right Quest target bridge is now a parameterized shared bridge, also exposed as `quest_target_bridge`. The right entry point remains. The left instance reads `/q2r_left_hand_pose` and `/q2r_left_hand_inputs`, publishes `/quest_left_target_pose` and `/quest_left_target_marker`, and leaves the target in Quest world. The RM basis conversion occurs only in the adapter.
- `teleop_status_monitor` is read-only and accepts per-arm topic parameters. The left launch uses a distinct adapter name `/left_rm65_teleop_adapter` and monitor name. It defaults `start_tcp=false` because an existing TCP endpoint may own port 10000; starting another endpoint requires a separate graph/port check.

## Left axes and mapping

- Operator-confirmed physical axes: Quest `+X=forward`, `+Y=left`, `+Z=up`; left RM65 base `+X=down`, `+Y=back`, `+Z=left`.
- Mathematically derived `M_left=[[0,0,-1],[-1,0,0],[0,1,0]]`; `M M^T=I`, `det(M)=+1`. Quest `+X→left -Y`, `+Y→left +Z`, `+Z→left -X`.
- Orientation retains world/base-frame left multiplication: `DeltaR_Q=R_Q R_Q0^T`; `DeltaR_L=M_left DeltaR_Q M_left^T`; `R_desired=DeltaR_L R_L0`. Tests cover the basis rotations, normalization, `q/-q` equivalence and non-commuting anchor order.
- **Left mapping hardware validation: pending.** The physical axes were confirmed by the operator; these equations were derived and tested in software only.

## Left safety configuration

- `dry_run=true`, `hardware_write_enabled=false`, `mapping_verified=false`, `home_enabled=false`. Face buttons are not mapped to left movement or Home. `press_middle` is exercised as a **software** deadman field; its left physical behavior has not been accepted on hardware.
- `home_joint_degrees` and `home_button_field` are absent from the left YAML. Left Home target, Home button, X/Y physical mapping, and workspace remain undecided.
- `workspace_min/max=[-10,-10,-10]/[10,10,10]` are finite **NOT HARDWARE-VALIDATED synthetic preview bounds**. They are not a left workspace proposal and cannot authorize hardware writes.
- Left dry-run publishes `/left/rm65_teleop/status` and, with fresh synthetic feedback and software Grip, `/left/rm65_teleop/preview_target_pose`. It creates no real `/left/rm_driver/movep_canfd_cmd` or `/left/rm_driver/move_stop_cmd` publisher and no real Home Action client.

## Validation performed

- RED before implementation: three left interface tests failed for missing node identities, left config and left launch. GREEN after implementation: targeted Python tests 31/31 and left quaternion tests 2/2; direct left dry-run probe 1/1; synthetic cross-arm ownership probe 1/1; existing right Home synthetic probe 2/2 after updating its stale one-point expectation to the already field-validated four-point trajectory.
- Four ROS packages (`quest2ros`, `ros_tcp_endpoint`, `q2r2_bringup`, `rm65_teleop_adapter`) built with system Python/colcon. Affected-package tests passed. Final full `colcon test-result --all`: **220 reported tests, 0 errors, 0 failures, 0 skipped** (this report includes 14 CTest wrapper records as well as their individual cases).
- All automated ROS tests used `ROS_DOMAIN_ID=143`, `ROS_LOCALHOST_ONLY=1`. The synthetic left probe fed left Quest pose/inputs and fake robot feedback on that isolated domain, reached `ARMED` then software `ACTIVE`, produced left target and preview, verified Quest +X translation/rotation toward left -Y, then left `ACTIVE` on Grip release. Counts on real left movep, movej, stop topics were zero; no left Home Action service client appeared.
- The isolated left launch command below started the bridge, adapter and read-only monitor, then shut down cleanly with exit 0. With no Quest or left robot feedback in that launch smoke, monitor correctly reported lost inputs/robot and adapter `DISABLED`; preview motion requires fresh feedback. The live domain-42 Quest left topics were seen read-only before development, but this stage did **not** connect the new left adapter to live Quest or real left feedback.

```bash
conda deactivate 2>/dev/null || true
source /opt/ros/humble/setup.bash
source /home/lh/robot/install/setup.bash
source /home/lh/quest2ros2_ws/.worktrees/left-rm65-teleop/install/setup.bash
export ROS_DOMAIN_ID=143
export ROS_LOCALHOST_ONLY=1
ros2 launch rm65_teleop_adapter left_quest_teleop.launch.py \
  mode:=dry_run use_rviz:=false start_tcp:=false
```

## Open before left hardware

- Confirm left Grip physical deadman behavior and X/Y physical button mapping; select Home and reserved/gripper controls separately. No right B binding is inherited.
- Record operator-approved left Home six-joint pose, left Cartesian absolute workspace, standalone safe pose, tool/load, cable constraints and left/right collision considerations. Generic RM65 URDF/MoveIt limits in `/home/lh/robot` do not establish these site-specific bounds.
- Perform a separate left-only runtime graph preflight and low-risk mapping validation under onsite authorization. Keep driver/control startups left-only. Quest/TCP input stability remains a separate open issue.
