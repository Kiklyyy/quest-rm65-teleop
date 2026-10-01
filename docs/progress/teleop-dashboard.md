# 双臂机器人遥操作监控系统

## Scope and baseline

- Branch: `feat/teleop-dashboard`.
- Baseline: fetched `origin/main`, including PR #9 merge
  `cc845f26ac2a6fee584d974ef59e446a3b730df1`.
- Package: `src/rm65_teleop_dashboard/`; internal name
  **Dual-Arm VR Teleoperation Dashboard**.
- Target runtime: Ubuntu 22.04, ROS 2 Humble, system Python 3.10
  (`/usr/bin/python3`) and PyQt5. Do not use Conda for ROS 2.
- **Dashboard is read-only.** It observes existing topics and reads the node
  graph. It does not start drivers, `rm_control`, Quest bringup or the hand SDK,
  create robot command publishers/services/action clients, issue Home/presets,
  or add a second robot safety state machine. The READ ONLY header is a status
  label; there is no GUI emergency-stop control.
- The existing adapter, hardware profiles, bringup and control mappings are
  unchanged. No real robot/hand motion is required to develop or run demo mode.

## Interface audit

Before implementation, the adapter source, existing monitor and pure monitor
logic, right LinkerHand node, dual launch, hardware YAML, `docs/INTERFACE.md`,
`STATUS.md` and dual-bringup progress were inspected at the main baseline.
The subscription contract below follows the code rather than the reference
image. RM65 has **six joints**; only the **right** LinkerHand is configured.

| Side | Topic | ROS 2 message |
|---|---|---|
| Left | `/q2r_left_hand_pose` | `geometry_msgs/msg/PoseStamped` |
| Left | `/q2r_left_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` |
| Left | `/quest_left_target_pose` | `geometry_msgs/msg/PoseStamped` |
| Left | `/left/rm_driver/udp_arm_position` | `geometry_msgs/msg/Pose` |
| Left | `/left/joint_states` | `sensor_msgs/msg/JointState` |
| Left | `/left/rm65_teleop/status` | `std_msgs/msg/String` JSON |
| Right | `/q2r_right_hand_pose` | `geometry_msgs/msg/PoseStamped` |
| Right | `/q2r_right_hand_inputs` | `quest2ros/msg/OVR2ROSInputs` |
| Right | `/quest_right_target_pose` | `geometry_msgs/msg/PoseStamped` |
| Right | `/right/rm_driver/udp_arm_position` | `geometry_msgs/msg/Pose` |
| Right | `/right/joint_states` | `sensor_msgs/msg/JointState` |
| Right | `/right/rm65_teleop/status` | `std_msgs/msg/String` JSON |
| Right hand | `/right/linkerhand/status` | `std_msgs/msg/String` JSON |

The existing Quest ROS TCP, target bridge and status publishers use depth 10
with the default reliable ROS QoS. Adapter status is published at about 10 Hz
and on state transitions; right-hand status defaults to 10 Hz. Feedback and
Quest receive frequency are measured locally rather than hard-coded in live
mode. All 13 dashboard subscriptions use BEST_EFFORT, KEEP_LAST depth 10 and
VOLATILE durability, compatible with the existing reliable publishers and
best-effort robot feedback publishers.

Raw Quest pose and inputs are monitored independently. Target bridges continue
publishing frozen targets with fresh stamps at 50 Hz; a fresh target does **not**
prove that Quest is online, Grip is pressed, or Cartesian motion is authorized.
Display freshness uses local monotonic receive time, not remote header time.

### Adapter JSON

The main-baseline payload supports:

```text
state
dry_run, hardware_write_enabled, hardware_output_available, mapping_verified
deadman_pressed, deadman_source
target_fresh, quest_pose_fresh, inputs_fresh, home_inputs_fresh
robot_fresh, joint_state_fresh
quest_pose_age_ms, inputs_age_ms, joint_preset_x_inputs_age_ms
robot_age_ms, joint_state_age_ms
rearm_count, watchdog_count
home_button_pressed, joint_presets_enabled
joint_preset_selection, joint_preset_active
home_hold_progress, home_action_state
command_path_ready, home_command_path_ready
max_cycle_period_ms, reason
```

Absent ages are emitted as `-1` by the adapter. Missing/old fields are displayed
as unknown/unavailable rather than interpreted as an affirmative state.
Malformed JSON or invalid values are surfaced as a data anomaly. Numeric values
are validated for finiteness before reaching widgets or progress bars.

Actual adapter states are `DISABLED`, `ARMED`, `ACTIVE`, `HOMING`,
`REARM_REQUIRED` and `FAULT`. Home action strings are `IDLE`, `PENDING`,
`ACTIVE`, `CANCELING`, `SUCCEEDED`, `CANCELED`, `REJECTED`, `ABORTED`,
`SERVER_UNAVAILABLE` and `DISABLED`. The actual right preset strings are
`NONE`, `X_FIRST`, `A_SECOND`, `B_LAST`, `CONFLICT` and `UNKNOWN`.

### Right LinkerHand JSON

```text
stamp
trigger_value, trigger_pressed, trigger_armed
hand_toggle_state
target, actual, fault_codes
communication_ok, input_fresh
dry_run, connect_only
state, error, invalid_input_count
```

`target` can be null at startup and in connect-only mode. In dry-run, `actual`
and `fault_codes` are null and `communication_ok` is false; unavailable data
must not appear as a successful real-hardware connection. Published hand states
include `READY`, `CONNECT_ONLY`, `INPUT_STALE`, `COMM_ERROR`, `HAND_FAULT` and
`DRY_RUN`. Loss of the status stream is displayed as OFFLINE/LOST.
The source `stamp` is ignored for health calculations; 14 semantic hand fields
are parsed, and a separate local monotonic receive timestamp tracks freshness.

The seven hand channels are `Thumb Pitch`, `Thumb Yaw`, `Index`, `Middle`,
`Ring`, `Little` and `Thumb Roll`, in that order. They are separate from the six
RM65 joints. The left end effector is shown as **Not Configured**; no left-hand
topic, data or SDK connection is fabricated.

### Read-only control mapping

| Controller | Observed field | Existing control behavior |
|---|---|---|
| Both | `press_middle` / Grip | Same-arm Cartesian teleop deadman |
| Left X | `button_lower` | Right preset 1 (`X_FIRST`) |
| Left Y | `button_upper` | Left Home |
| Right index | `press_index` | Right LinkerHand toggle |
| Right A | `button_lower` | Right preset 2 (`A_SECOND`) |
| Right B | `button_upper` | Right preset 3 (`B_LAST`) |

The GUI displays these mappings and raw analog/button values. It does not
interpret button edges into robot/hand commands.

## Architecture and UI

The package separates pure data models/JSON parsing, ROS acquisition and Qt
presentation. `SnapshotStore` protects state with a lock and returns copies.
The background rclpy executor only updates data; it never touches a QWidget.
The Qt main thread consumes snapshots with a 100 ms QTimer (10 Hz). Shutdown
stops the executor, joins the worker, destroys its node and shuts down its
dedicated rclpy context. ROS logging/parameter services are disabled and the
automatic Humble parameter-events publisher is removed, so the monitor's
runtime node exposes subscription endpoints only.
Demo mode uses the same snapshot/UI path without importing ROS or the hand SDK.

The dark 16:9 layout uses Qt layouts/splitters and centralized QSS. It includes:

- Header: Chinese software name, ROS domain, adapter-derived operating mode,
  local clock, overall display-only health and READ ONLY / DEMO DATA badges.
- System overview: separate Quest streams, ROS graph, left/right RM65 feedback,
  right hand, watchdog/fault summary and left end-effector availability.
- Arm cards: real TCP XYZ in metres, quaternion/RPY in degrees, reordered
  `joint1..joint6`, receive/adapter ages, deadman, command paths and reason.
  Joint bars use a clearly labeled **display range ±180°**, not robot limits.
- Robot overview: a QPainter abstract dual six-axis robot; no CAD/OpenGL/RViz
  dependency and no claim of accurate kinematics.
- VR inputs: pose, RPY, frequency/age, Grip/index percentages and X/Y or A/B.
- Safety/command paths: observed adapter state, Cartesian/Home readiness,
  watchdog/rearm counters, maximum cycle period, Home hold/action and presets.
- Right L7: communication/input health, toggle/trigger status, target/actual
  seven-channel bars, faults and error.
- Local event log: state changes with time/level/source/message, bounded
  retention and All/Info/Warning/Error filters. It does not collect ROS console.

There are no active Home, preset or hand open/close buttons. Stale status is
visibly marked and cannot continue presenting a last-known READY/ACTIVE label
as current. Overall SYSTEM READY/DEGRADED/FAULT/OFFLINE is a UI summary only.
Unknown adapter states and missing/invalid core streams degrade this display
summary. An absent optional right-hand node does not degrade the arm system;
a present hand with stale/invalid data or INPUT_STALE does. These rules never
send commands or authorize motion.

## Run and capture

Check the system Qt installation first:

```bash
/usr/bin/python3 -c "import PyQt5; print(PyQt5.__file__)"
```

If missing, use the Ubuntu system package `python3-pyqt5` (apt), keeping ROS 2
on `/usr/bin/python3`. Do not install GUI dependencies into Conda.

After sourcing ROS 2 and building this package:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run rm65_teleop_dashboard teleop_dashboard --demo
```

Without ROS, demo can run directly from the source tree with system Python:

```bash
PYTHONPATH=src/rm65_teleop_dashboard \
  /usr/bin/python3 -m rm65_teleop_dashboard.app --demo
```

Demo generates dynamic, visibly labeled DEMO DATA, including left ACTIVE/right
ARMED, 72 Hz Quest and 198 Hz feedback, exactly six arm joints, TCP/orientation,
analog controls, Home path status and right hand OPEN/CLOSED. Synthetic values
remain in memory and are never published to ROS.

Normal ROS monitoring is a separate terminal from the existing teleop system:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=42   # match the existing teleop system
ros2 launch rm65_teleop_dashboard dashboard.launch.py
# Or: ros2 run rm65_teleop_dashboard teleop_dashboard
```

Launch defaults to `demo:=false` and starts only the dashboard. It does not
include `dual_quest_teleop.launch.py` or any driver/control/SDK launch.

Offscreen capture:

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=src/rm65_teleop_dashboard \
  /usr/bin/python3 -m rm65_teleop_dashboard.app \
  --demo --screenshot /tmp/teleop-dashboard.png
```

The application waits about one second, captures the actual MainWindow as PNG
and exits through normal cleanup. No pixel-comparison test is required.

## Verification record

Local implementation checks and isolated Ubuntu validation passed. The
workspace software regression excludes only the unavailable onsite SDK
transport group described below. The table distinguishes the evidence obtained.

| Check | Current evidence |
|---|---|
| Main interface audit | Completed against PR #9 baseline source |
| Dashboard local tests | Windows isolated Python: 26 passed, 1 skipped (ROS unavailable), 4 subtests passed; includes pure models/parsers/demo, static contracts and Qt smoke/layout/filter/stale checks |
| Independent pure/static checkpoint | Windows pytest: 19 passed, 4 subtests passed (models, status parsing, demo, read-only/launch source contract) |
| Existing pure Python regression | Windows pytest: 69 passed in 0.25 s (Quest target, existing status monitor, right-hand toggle logic) |
| Qt offscreen smoke and screenshots | Passed locally; window sizes 1920×1080, 1600×900, 1366×768 and 1280×720 tested; final PNGs captured and visually inspected |
| Read-only static/package review | Runtime source review found exactly 13 subscriptions and no control publishers/services/action clients; static contract tests passed |
| Dashboard / affected workspace build | Ubuntu 22.04 / Humble CI: five-package build passed in 34.3 s; dashboard-selected build passed in 1.08 s |
| Dashboard Ubuntu tests | Linux Python 3.10.12 / system PyQt5: 27 passed in 0.92 s, no skips |
| Five-package software regression | colcon test passed in 27.9 s; 295 reported tests, 0 errors, 0 failures, 0 skipped; includes the 27 dashboard tests and 19/19 adapter CTest groups; onsite SDK transport group excluded as described below |
| Actual rclpy data acquisition | Isolated 13-topic receive probe passed: named six-joint ordering, Quest/robot receipt rates, malformed JSON, stale suppression, zero monitor output endpoints and clean executor/thread/context shutdown |
| Hardware actions | None; no RM driver, rm_control, SDK or motion started |

Reproducible Ubuntu checks:

```bash
source /opt/ros/humble/setup.bash
source /home/lh/robot/install/setup.bash
test "$(command -v python3)" = /usr/bin/python3
/usr/bin/colcon build --symlink-install --packages-select rm65_teleop_dashboard
/usr/bin/colcon test --packages-select rm65_teleop_dashboard
/usr/bin/colcon test-result --all --verbose

/usr/bin/colcon build --symlink-install --packages-select \
  quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter rm65_teleop_dashboard
ROS_DOMAIN_ID=143 ROS_LOCALHOST_ONLY=1 \
  /usr/bin/colcon test --packages-select \
  quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter rm65_teleop_dashboard
/usr/bin/colcon test-result --all --verbose
```

Onsite ROS integration is distinct from isolated subscription delivery and demo
checks. The robot host was unavailable through SSH in this session; the UI has
not been deployed there or connected to live Quest/robot/hand feedback.

The partial Windows regression above used an isolated validation environment
outside the worktree; it did not alter Conda or the Ubuntu system. It covers
`src/Quest2ROS2/test/test_quest_right_target_logic.py`,
`src/rm65_teleop_adapter/test/test_teleop_status_logic.py` and
`src/rm65_teleop_adapter/test/test_right_linkerhand_logic.py`. ROS launch,
generated messages and C++ adapter tests run separately in the Ubuntu ROS
environment. Onsite SDK transport tests require the unavailable vendor SDK;
CI does not claim to validate the SDK or physical robot behavior.

Windows offscreen validation needed explicit discovery of the installed local
Qt platform plugins because a non-ASCII virtualenv path was not resolved by the
wheel's default Qt configuration. A fallback loads existing system fonts only
when offscreen font enumeration is empty. Normal desktop/Ubuntu font discovery
is unchanged; there are no online fonts or icon downloads.

The CI workflow `.github/workflows/teleop-dashboard.yml` uses Ubuntu 22.04,
the `ros:humble-ros-base-jammy` container, `/usr/bin/python3` and apt
`python3-pyqt5`. It builds the official `rm_ros_interfaces` message package
only, pinned to RealMan source `c941b565e4f9174afa36561f143ef5fbbb744750`;
vendor driver/control binaries and the hand SDK are not built or started.
It then builds all five affected workspace packages and the dashboard selected
package, runs dashboard tests and `tools/dashboard_ros_probe.py`, runs the
five-package software regression and captures three desktop sizes.
The receive probe is outside the dashboard package and requires domain 143
with localhost-only networking; its fixture publishes only feedback/input/status
messages to exercise actual rclpy subscriptions, never robot command topics.

The CI regression excludes exactly the existing CTest group
`test_right_linkerhand_transport` (three pytest cases). This group requires the
unversioned onsite RealMan tool-RS485 SDK at
`/home/lh/quest2ros2_ws/linkerhand/linker_hand_python_sdk`, which is absent from
CI. An initial run reached this unchanged test and recorded two expected
unavailable-SDK skips plus one `ModuleNotFoundError: LinkerHand` in its full-SDK
constructor case. The file is byte-identical on main and the dashboard branch
(Git blob `3a5dad4d69dd3ac379506cfcc23df5a5a892d195`); it was not weakened or
edited. Every repository-contained adapter, launch, Home/preset, watchdog and
hand-toggle software test remains enabled. This exclusion is an external test
dependency limitation, not an SDK pass claim. No hand SDK was installed,
connected or used, and its transport behavior remains unverified in CI.

## Demo screenshots

These PNGs are captures of the running Qt application with explicitly labeled
DEMO DATA, not mockups or live-hardware evidence:

- [1920 × 1080](../screenshots/teleop-dashboard-demo-1920x1080.png)
- [1366 × 768](../screenshots/teleop-dashboard-demo-1366x768.png)

At 1920 × 1080 the two six-joint arm cards, robot drawing, both controllers,
safety fields and all seven right-hand channels are visible. Smaller desktop
sizes keep the layout usable with per-column scrolling; the 1366 screenshot
shows the initial viewport rather than every scrollable field.

## Verified source and deployment boundary

The verified application-code baseline is
`b1402b774e6a22d6ba7c3e0bf21cac29924c52b9` on `feat/teleop-dashboard`:
[GitHub Actions run 36882727720](https://github.com/Kiklyyy/quest-rm65-teleop/actions/runs/36882727720).
**Result: SUCCESS.** The workflow verifies the selected dashboard build,
five-package build, all dashboard tests, actual 13-topic ROS receive probe,
five-package software regression and demo captures. Source synchronization does
not deploy to the onsite robot host, restart the teleop stack or enable hardware.
