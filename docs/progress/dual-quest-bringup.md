# Dual Quest bringup progress

## Scope

- Branch: `feat/dual-quest-bringup`.
- Baseline: current `origin/main`, fast-forwarded to the pushed
  `origin/feat/right-linkerhand-quest` so the same tree contains left RM65
  teleop, right RM65 teleop/Home, and right O7 Quest toggle.
- Goal: replace the manually started left/right `rm_driver`, left/right
  `rm_control`, right Quest launch, and left Quest launch with one parent launch.
- `/home/lh/robot` is a read-only dependency and was not changed.

## Launch composition

`rm65_teleop_adapter/launch/dual_quest_teleop.launch.py` reuses:

1. `rm_driver/launch/rm_65_dual_driver.launch.py`;
2. `rm_control/launch/rm_65_dual_control.launch.py`;
3. `rm65_teleop_adapter/launch/right_quest_teleop.launch.py`;
4. `rm65_teleop_adapter/launch/left_quest_teleop.launch.py`.

The dual RM launch configuration matches the previously used manual commands:
left controller `169.254.128.18:8080` with host UDP port `8089`, right controller
`169.254.128.19:8080` with host UDP port `8090`, and namespaced control Actions
under `/left` and `/right`. The right child alone may start ROS TCP port 10000;
the left child is always passed `start_tcp:=false`.

Dry-run starts the two Quest adapter chains without creating RM driver/control
processes. Hardware mode starts both dual RM launch files unless explicitly
disabled. `safe` and `normal` are the only shared profiles because left
hardware rejects the unvalidated right-only `fast` profile.

Both adapter processes now use `config/hardware.yaml`. A ROS 2 `/**` block
stores common hardware gates, watchdogs, timing, motion safety limits and the
temporary workspace once. Right/left node blocks contain only their endpoints,
mapping matrix, preview frame and independent Home target/Action. The former
duplicate `left_hardware.yaml` is removed.

The right hardware block also contains the operator-supplied joint presets:
X/left `button_lower` selects `quest_right_first`, A/right `button_lower`
selects `quest_right_second`, and B/right `button_upper` selects
`quest_right_last`. The adapter reuses its existing guarded four-point right
joint Action path. A held-at-startup button, multiple buttons, or changing the
selection without a full release cannot create a goal. The prior single right
B/Home target is superseded; the left Y/Home target is unchanged.

## Safety boundary

The optional right O7 node stays off by default. Existing onsite evidence shows
that enabling its second RealMan API2/tool-RS485 connection correlates with the
right arm's first Grip command moving toward an old pose. This change does not
fix or bypass that issue. `start_linkerhand:=true` remains an explicit operator
choice, and `linkerhand_connect_only:=true` is accepted only in hardware mode
with the hand node enabled.

## Verification

- Source-level launch contract: defaults, one TCP owner, child driver startup
  disabled, verified dual RM launch reuse, shared-profile validation and O7
  connect-only gate.
- Four-package `colcon build --symlink-install` passed. The final isolated
  regression reports 266 tests, 0 errors, 0 failures and 0 skipped; the new
  dual-launch contract contributes 7 passing tests.
- Isolated hardware-mode parameter loading started only the two adapters, with
  driver/control/TCP/bridges/O7 disabled. Both received common
  `control_rate_hz=200.0` and workspace `[-1,-1,0]`; their driver identities,
  mapping matrices and Home Actions remained correctly right/left-specific.
  Both processes exited cleanly, and no real driver or control node was started.
- Focused tests cover X/A/B mapping, release/conflict latching and the extra
  Quest input watchdog. The synthetic Action graph reached the exact three
  configured final joint arrays while retaining zero Cartesian commands and
  zero real publishers. These targets have no real-robot validation yet.
- Isolated domain 143 dry-run started both adapters, both Quest target bridges
  and the optional O7 dry-run node. `/left/rm_driver/movep_canfd_cmd` and
  `/right/rm_driver/movep_canfd_cmd` were absent, and all five processes exited
  cleanly on Ctrl-C.
- The O7 node now ignores the expected launch-time `KeyboardInterrupt` and
  avoids a duplicate ROS shutdown, so a unified Ctrl-C is clean. Its focused
  ROS test file passes 13/13 tests after this change.
- No real driver, controller, Quest endpoint, hand SDK connection, command or
  robot motion was started while implementing this checkpoint.
