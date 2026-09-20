# rm65_teleop_adapter

B-side safety adapter for Quest right-hand translation to the right RealMan RM65.

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
The checked-in hardware profile uses `follow=false`, a nominal 200 Hz timer,
5 mm/s velocity limit, 0.05 mm per-step limit, 3 cm anchor radius, and a 50 ms
control-stall fault. Dry-run remains the default launch mode.

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

Simulation publishers must be remapped to test-only topics; do not inject simulated data into live Quest topics.

## Run hardware mode

Only after the right-arm driver, workspace, emergency stop, unique command source,
and live Quest inputs have been checked:

```bash
ros2 launch rm65_teleop_adapter hardware.launch.py
```
