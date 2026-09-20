# rm65_teleop_adapter

B-side safety adapter for Quest right-hand translation to the right RealMan RM65.

This first milestone is **dry-run only**. It publishes:

- `/right/rm65_teleop/preview_target_pose`
- `/right/rm65_teleop/status`

It intentionally contains no publisher for `/right/rm_driver/movep_canfd_cmd` or `/right/rm_driver/move_stop_cmd`. Setting `dry_run=false` or `hardware_write_enabled=true` makes the node refuse to start.

The first-stage enable source is `/q2r_right_hand_inputs.button_lower`. The adapter independently watches target, raw Quest Pose, Inputs, and robot feedback receipt times. After release or any timeout, data recovery cannot resume ACTIVE until a new release-to-press sequence captures fresh Quest and robot anchors.

The checked-in mapping is identity because A-side field validation established `+X=forward`, `+Y=left`, `+Z=up`. `mapping_verified` remains false until the RM65 base-frame physical directions are separately confirmed on site.

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
