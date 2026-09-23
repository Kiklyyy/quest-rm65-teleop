# Right-arm Home and stability progress

Branch: `feat/recenter-home`. Worktree: `/home/lh/quest2ros2_ws/.worktrees/recenter-home`.

## Confirmed input mapping

- Physical A -> `button_lower`; reserved in this phase.
- Physical B -> `button_upper`; selected by `home_button_field: upper`.
- Source: operator-confirmed existing Quest2ROS2 mapping; A was the former pre-trigger deadman button.
- Grip `press_middle` remains the teleop deadman and release -> press remains the effective re-anchor.

## Validation boundary

real RM65 Home validation = pending. No real Home goal or RM driver will be started in this phase.
