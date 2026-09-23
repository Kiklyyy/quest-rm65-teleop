# Right-arm Home and Stability Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a B-hold, hold-to-run right-RM65 Home operation with strict mutual exclusion against Cartesian Quest teleoperation, while preserving existing Grip re-anchor semantics and adding enough observability to diagnose watchdog/rearm events.

**Architecture:** Extend the existing `AdapterLogic` state machine with a `HOMING` mode and one-shot B-hold gate, but keep ROS action transport outside the pure logic. A focused Home trajectory helper validates/reorders six joint inputs and computes a speed-bounded one-point trajectory plan; a focused Home action client owns only `FollowJointTrajectory` send/cancel/result transport. The production adapter remains the sole arbiter: `ACTIVE` may stream Cartesian poses, `HOMING` may own the joint action, and neither path may command in the other mode.

**Tech Stack:** ROS 2 Humble, C++17, `rclcpp`, `rclcpp_action`, `control_msgs/action/FollowJointTrajectory`, `sensor_msgs/msg/JointState`, `trajectory_msgs/msg/JointTrajectoryPoint`, GTest, ament/colcon, Python 3.10 pytest for status/config tests.

**Spec:** `docs/superpowers/specs/2026-09-23-right-arm-recenter-home-design.md`

## Global Constraints

- Middle-finger Grip remains the teleoperation deadman and existing release -> press re-anchor behavior remains the only motion recenter operation.
- Physical A/B mapping must be measured from real Quest input; do not guess `button_upper` versus `button_lower`.
- A remains reserved and has no robot-state or motion authority in this feature.
- Home starts only from `ARMED`, with Grip released, after B has been held continuously for at least `1.5 s`.
- B must remain held for the entire Home motion; release requests cancel and stop.
- Quest pose, Quest inputs, robot pose, and joint-state freshness are required throughout Home.
- Home uses `/right/rm_group_controller/follow_joint_trajectory`; Cartesian `/right/rm_driver/movep_canfd_cmd` is forbidden while `HOMING`.
- Temporary Home target, in degrees: `[-95.605, 4.406, -80.034, -22.695, -48.462, 97.570]`.
- Home nominal speed: `15.0 deg/s`; target/timing values are parameters, never hard-coded motion constants.
- Home success ends in `REARM_REQUIRED`; teleoperation never resumes automatically.
- Existing translation/orientation mapping, watchdog thresholds, workspace limits, deadman thresholds, stop behavior, motion profiles, and single Cartesian command path remain unchanged.
- No gripper, left arm, dual-arm coordination, MoveIt/CuRobo planning, collision avoidance, or ACTIVE-session manual Recenter behavior is added.

## Review Focus

- **Cancel acknowledgement race:** B release or watchdog loss must suppress Cartesian output immediately and keep the adapter out of `ARMED/ACTIVE` until the Home action reaches a terminal result; test this in Task 3.
- **Continuous-B retrigger:** a successful/canceled Home while B remains held must not issue a second Home goal; test one-shot latching and release-to-rehold in Task 3.
- **Joint name/order mismatch:** Home target J1..J6 must map by verified configured joint names, not incidental `JointState` array order; test shuffled and missing names in Task 2.
- **Action transport failure:** rejected/aborted goals and unavailable action server must not leave a latent Home motion path or resume teleop; test transport outcomes in Task 4.
- **Dry-run/hardware isolation:** dry-run must never create or send to the real Home action path; test configuration/node gates in Task 5.

---

### Task 1: Verify and lock the physical Quest A/B binding

**Files:**
- Create: `src/rm65_teleop_adapter/include/rm65_teleop_adapter/quest_face_button.hpp`
- Create: `src/rm65_teleop_adapter/test/test_quest_face_button.cpp`
- Modify: `src/rm65_teleop_adapter/CMakeLists.txt`
- Create: `docs/progress/right-arm-recenter-home.md`
- Later in this task, after the live probe: `src/rm65_teleop_adapter/config/hardware.yaml`

**Interfaces:**
- Produces:
  - `enum class QuestFaceButtonField {UPPER, LOWER};`
  - `std::optional<QuestFaceButtonField> parse_quest_face_button_field(std::string_view value);`
  - `template<typename InputsT> bool quest_face_button_pressed(const InputsT &, QuestFaceButtonField);`
  - hardware parameter `home_button_field: "upper"|"lower"`, set only from observed physical B mapping.

- [ ] **Step 1: Write the failing parser/selector tests**

Create `test_quest_face_button.cpp` with tests equivalent to:

```cpp
struct FakeInputs {
  bool button_upper{false};
  bool button_lower{false};
};

TEST(QuestFaceButton, ParsesOnlyUpperAndLower)
{
  EXPECT_EQ(parse_quest_face_button_field("upper"), QuestFaceButtonField::UPPER);
  EXPECT_EQ(parse_quest_face_button_field("lower"), QuestFaceButtonField::LOWER);
  EXPECT_FALSE(parse_quest_face_button_field("unverified").has_value());
  EXPECT_FALSE(parse_quest_face_button_field("").has_value());
}

TEST(QuestFaceButton, SelectsRequestedWireField)
{
  FakeInputs inputs;
  inputs.button_upper = true;
  EXPECT_TRUE(quest_face_button_pressed(inputs, QuestFaceButtonField::UPPER));
  EXPECT_FALSE(quest_face_button_pressed(inputs, QuestFaceButtonField::LOWER));

  inputs.button_upper = false;
  inputs.button_lower = true;
  EXPECT_FALSE(quest_face_button_pressed(inputs, QuestFaceButtonField::UPPER));
  EXPECT_TRUE(quest_face_button_pressed(inputs, QuestFaceButtonField::LOWER));
}
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
/usr/bin/colcon --log-base log build --build-base build --install-base install   --packages-select rm65_teleop_adapter --symlink-install
/usr/bin/colcon --log-base log test --build-base build --install-base install   --packages-select rm65_teleop_adapter --ctest-args -R test_quest_face_button --output-on-failure
```

Expected: compile/test failure because the face-button API does not exist.

- [ ] **Step 3: Implement the minimal face-button helper**

Create a small header-only selector plus parser declaration/definition in the same header:

```cpp
enum class QuestFaceButtonField {UPPER, LOWER};

inline std::optional<QuestFaceButtonField>
parse_quest_face_button_field(std::string_view value)
{
  if (value == "upper") return QuestFaceButtonField::UPPER;
  if (value == "lower") return QuestFaceButtonField::LOWER;
  return std::nullopt;
}

template<typename InputsT>
bool quest_face_button_pressed(
  const InputsT & input, QuestFaceButtonField field)
{
  return field == QuestFaceButtonField::UPPER ?
         static_cast<bool>(input.button_upper) :
         static_cast<bool>(input.button_lower);
}
```

Add the GTest target to CMake.

- [ ] **Step 4: Run focused test and verify GREEN**

Run the same focused test. Expected: PASS.

- [ ] **Step 5: Perform the real Quest no-motion A/B probe**

Use the real Quest with the RM driver and hardware adapter **not running**. Source the normal ROS 2 / Quest workspace and observe:

```bash
ros2 topic echo /q2r_right_hand_inputs
```

Press only physical A several times, then only physical B several times. Record exactly which field toggles for each physical button.

Acceptance:
- A and B each map unambiguously to one of `button_upper` / `button_lower`.
- If the mapping is ambiguous, stop the plan here and do not enable Home.

- [ ] **Step 6: Record the measured mapping and lock only physical B into config**

In `docs/progress/right-arm-recenter-home.md`, record:

```text
Physical A -> observed message field
Physical B -> observed message field
Probe date/time and that RM driver / hardware teleop were not running
```

In `hardware.yaml`, add `home_button_field` with the exact observed physical-B literal, `"upper"` or `"lower"`. Do not add an A behavior.

- [ ] **Step 7: Commit**

```bash
git add src/rm65_teleop_adapter/include/rm65_teleop_adapter/quest_face_button.hpp         src/rm65_teleop_adapter/test/test_quest_face_button.cpp         src/rm65_teleop_adapter/CMakeLists.txt         src/rm65_teleop_adapter/config/hardware.yaml         docs/progress/right-arm-recenter-home.md
git commit -m "feat: verify Quest Home button binding"
```

---

### Task 2: Add validated Home joint configuration and trajectory planning

**Files:**
- Create: `src/rm65_teleop_adapter/include/rm65_teleop_adapter/home_trajectory.hpp`
- Create: `src/rm65_teleop_adapter/src/home_trajectory.cpp`
- Create: `src/rm65_teleop_adapter/test/test_home_trajectory.cpp`
- Modify: `src/rm65_teleop_adapter/CMakeLists.txt`
- Modify: `src/rm65_teleop_adapter/config/hardware.yaml`

**Interfaces:**
- Produces:

```cpp
struct HomeTrajectoryConfig {
  std::array<double, 6> target_degrees;
  std::array<std::string, 6> joint_names;
  double speed_deg_s{15.0};
  double hold_seconds{1.5};
};

struct HomeTrajectoryPlan {
  std::array<std::string, 6> joint_names;
  std::array<double, 6> target_radians;
  double duration_seconds{0.0};
};

bool home_trajectory_config_valid(const HomeTrajectoryConfig &);
std::optional<std::array<double, 6>> reorder_joint_positions(
  const std::vector<std::string> & message_names,
  const std::vector<double> & message_positions,
  const std::array<std::string, 6> & required_names);
std::optional<HomeTrajectoryPlan> make_home_trajectory_plan(
  const std::array<double, 6> & current_radians,
  const HomeTrajectoryConfig & config);
```

- [ ] **Step 1: Write RED tests for validation, name mapping, and timing**

Tests must pin all of these:

```cpp
TEST(HomeTrajectory, AcceptsTemporaryConfiguredTarget)
{
  HomeTrajectoryConfig cfg = valid_config();
  EXPECT_TRUE(home_trajectory_config_valid(cfg));
}

TEST(HomeTrajectory, RejectsNonFiniteTargetDuplicateOrEmptyNamesAndNonPositiveSpeed)
{
  // NaN in target -> false
  // duplicate name -> false
  // empty name -> false
  // speed <= 0 -> false
  // hold_seconds <= 0 -> false
}

TEST(HomeTrajectory, ReordersShuffledJointStateByConfiguredName)
{
  const std::vector<std::string> names{"j3","j1","j6","j2","j5","j4"};
  const std::vector<double> positions{3,1,6,2,5,4};
  const std::array<std::string,6> required{"j1","j2","j3","j4","j5","j6"};
  EXPECT_EQ(*reorder_joint_positions(names, positions, required),
            (std::array<double,6>{1,2,3,4,5,6}));
}

TEST(HomeTrajectory, MissingOrDuplicateJointStateNameIsRejected)
{
  // missing required name -> nullopt
  // duplicate message name -> nullopt
  // names/positions length mismatch -> nullopt
}

TEST(HomeTrajectory, DurationUsesFarthestJointAtFifteenDegreesPerSecond)
{
  // current all zero, target [30, 0, ...] deg -> 2.0 s
}

TEST(HomeTrajectory, NearHomeMinimumDurationCanOnlySlowTheMove)
{
  // tiny non-zero delta must result in positive duration that is
  // >= delta/speed; it may use the implementation minimum.
}
```

- [ ] **Step 2: Run focused test and verify RED**

Run GTest `test_home_trajectory`. Expected: missing symbols/files.

- [ ] **Step 3: Implement the minimal pure helper**

Rules:
- convert degrees with `rad = deg * pi / 180`
- validate all six target values finite
- validate six configured names are non-empty and unique
- validate speed and hold duration finite and `> 0`
- reorder incoming positions strictly by configured name
- reject duplicate/missing names or non-finite positions
- `duration = max(max_abs_delta_rad / speed_rad_s, 0.1)`; the `0.1 s` minimum can only make a move slower.

- [ ] **Step 4: Run focused tests and existing adapter logic regression**

Expected: new test GREEN; existing adapter logic tests unchanged and GREEN.

- [ ] **Step 5: Read the real right joint names without commanding motion**

With the verified right RM driver connected but no teleop/Home command source active:

```bash
ros2 topic echo /right/joint_states --once
```

Record all six exact `name[]` entries in `docs/progress/right-arm-recenter-home.md`.

Set `home_joint_names` in `hardware.yaml` to those six names in J1..J6 semantic order. Do not rely on incidental runtime array order.

Also add:

```yaml
home_enabled: true
home_hold_seconds: 1.5
home_speed_deg_s: 15.0
home_joint_degrees: [-95.605, 4.406, -80.034, -22.695, -48.462, 97.570]
home_action_name: /right/rm_group_controller/follow_joint_trajectory
joint_state_topic: /right/joint_states
joint_state_timeout: 0.10
```

Keep `dry_run.yaml` with `home_enabled: false`.

- [ ] **Step 6: Commit**

```bash
git add src/rm65_teleop_adapter/include/rm65_teleop_adapter/home_trajectory.hpp         src/rm65_teleop_adapter/src/home_trajectory.cpp         src/rm65_teleop_adapter/test/test_home_trajectory.cpp         src/rm65_teleop_adapter/CMakeLists.txt         src/rm65_teleop_adapter/config/hardware.yaml         src/rm65_teleop_adapter/config/dry_run.yaml         docs/progress/right-arm-recenter-home.md
git commit -m "feat: add validated Home trajectory planning"
```

---

### Task 3: Extend AdapterLogic with HOMING arbitration and B hold-to-run semantics

**Files:**
- Modify: `src/rm65_teleop_adapter/include/rm65_teleop_adapter/adapter_logic.hpp`
- Modify: `src/rm65_teleop_adapter/src/adapter_logic.cpp`
- Modify: `src/rm65_teleop_adapter/test/test_adapter_logic.cpp`
- Modify: `src/rm65_teleop_adapter/test/test_input_deadman.cpp`

**Interfaces:**
- Add:

```cpp
enum class HomeActionEvent {
  NONE,
  SUCCEEDED,
  CANCELED,
  REJECTED,
  ABORTED
};
```

- Extend `AdapterState` with `HOMING`.
- Extend `AdapterConfig` with `home_hold_seconds`.
- Extend `CycleInput`:

```cpp
bool home_button_pressed{false};
bool joint_state_fresh{false};
bool joint_state_valid{false};
bool home_action_ready{false};
bool home_plan_valid{false};
HomeActionEvent home_action_event{HomeActionEvent::NONE};
```

- Extend `CycleOutput`:

```cpp
bool home_goal_requested{false};
bool home_cancel_requested{false};
double home_hold_progress{0.0};
```

**Behavioral contract:**
- `ARMED + Grip released + B continuously held + all Home preconditions` accumulates hold time.
- crossing `home_hold_seconds` exactly once requests Home and enters `HOMING`.
- `HOMING` never emits Cartesian `command`.
- release/watchdog loss in HOMING requests cancel+stop once but remains `HOMING` until action terminal event arrives.
- `SUCCEEDED` and acknowledged `CANCELED` -> `REARM_REQUIRED`.
- `REJECTED` or `ABORTED` -> `FAULT`.
- B must be released before another Home request can be generated.
- Grip presses in `HOMING` are ignored for motion authorization.

- [ ] **Step 1: Write the state-machine RED tests**

Add tests covering:

```cpp
TEST(AdapterLogic, HomeHoldShorterThanThresholdDoesNotStart)
TEST(AdapterLogic, HomeStartsExactlyOnceAtHoldThreshold)
TEST(AdapterLogic, GripPressedBlocksHome)
TEST(AdapterLogic, HomeRequiresFreshJointStateAndReadyAction)
TEST(AdapterLogic, HomingNeverEmitsCartesianCommand)
TEST(AdapterLogic, HomeButtonReleaseRequestsCancelAndStaysHomingUntilCanceled)
TEST(AdapterLogic, HomeWatchdogLossRequestsCancelAndStaysHomingUntilTerminal)
TEST(AdapterLogic, HomeSuccessEntersRearmRequired)
TEST(AdapterLogic, HomeRejectedOrAbortedFaults)
TEST(AdapterLogic, HeldButtonCannotRetriggerAfterHomeTerminal)
TEST(AdapterLogic, NewHomeRequiresButtonReleaseThenFreshHold)
TEST(AdapterLogic, GripDuringHomingCannotActivateCartesianTeleop)
```

The cancel-ack race test must assert:

```cpp
auto out = logic.update(input_with_home_button_released);
EXPECT_EQ(out.state, AdapterState::HOMING);
EXPECT_TRUE(out.home_cancel_requested);
EXPECT_TRUE(out.stop_requested);
EXPECT_FALSE(out.command.has_value());

input.home_action_event = HomeActionEvent::CANCELED;
out = logic.update(input);
EXPECT_EQ(out.state, AdapterState::REARM_REQUIRED);
```

- [ ] **Step 2: Run focused tests and verify RED**

Run `test_adapter_logic` and `test_input_deadman`. Expected: failures because HOMING fields/state do not exist.

- [ ] **Step 3: Implement the minimal HOMING state logic**

Implementation details:
- add internal `home_hold_elapsed_seconds_`, `home_request_latched_`, `home_cancel_pending_`
- reset hold elapsed whenever B is released or an ARMED Home precondition becomes false
- set `home_request_latched_=true` when the threshold generates a goal
- do not clear the latch until a physical B release is observed
- while cancel is pending, do not emit repeated cancel requests
- keep `state_ == HOMING` until a terminal action event arrives
- existing ACTIVE deadman/release/watchdog behavior must remain byte-for-byte equivalent in effect.

Use specific cancellation reasons:
- `home_button_released`
- `home_quest_pose_not_fresh`
- `home_inputs_not_fresh`
- `home_robot_not_fresh`
- `home_joint_state_not_fresh`
- `home_joint_state_invalid`

Use fault reasons:
- `home_goal_rejected`
- `home_goal_aborted`

- [ ] **Step 4: Run focused GREEN tests and full existing AdapterLogic regression**

Expected: all Task 3 tests pass; all pre-existing translation/orientation/deadman tests remain green.

- [ ] **Step 5: Commit**

```bash
git add src/rm65_teleop_adapter/include/rm65_teleop_adapter/adapter_logic.hpp         src/rm65_teleop_adapter/src/adapter_logic.cpp         src/rm65_teleop_adapter/test/test_adapter_logic.cpp         src/rm65_teleop_adapter/test/test_input_deadman.cpp
git commit -m "feat: add Home state arbitration"
```

---

### Task 4: Add focused FollowJointTrajectory action transport

**Files:**
- Create: `src/rm65_teleop_adapter/include/rm65_teleop_adapter/home_action_client.hpp`
- Create: `src/rm65_teleop_adapter/src/home_action_client.cpp`
- Create: `src/rm65_teleop_adapter/test/test_home_action_client.cpp`
- Modify: `src/rm65_teleop_adapter/CMakeLists.txt`
- Modify: `src/rm65_teleop_adapter/package.xml`

**Interfaces:**
- Dependencies: `rclcpp_action`, `control_msgs`, `sensor_msgs`, `trajectory_msgs`.
- Produce a transport class:

```cpp
class HomeActionClient {
public:
  using FollowJT = control_msgs::action::FollowJointTrajectory;
  using EventCallback = std::function<void(HomeActionEvent)>;

  HomeActionClient(
    rclcpp::Node & node,
    const std::string & action_name,
    EventCallback callback);

  bool server_ready() const;
  bool goal_active() const;
  bool send_goal(const HomeTrajectoryPlan & plan);
  bool request_cancel();
};
```

`send_goal()` returns false if there is already a goal or the server is unavailable. The class emits `REJECTED`, `SUCCEEDED`, `CANCELED`, or `ABORTED` through the callback.

- [ ] **Step 1: Write a synthetic action-server RED integration test**

Create a GTest with a local `rclcpp_action::Server<FollowJointTrajectory>` at a test-only action name such as:

```text
/test/right/rm_group_controller/follow_joint_trajectory
```

Cover:
- client sees server ready
- one plan sends one goal with the exact six names, target radians, and `time_from_start`
- second send while active is rejected locally
- cancel request reaches the server and reports `CANCELED`
- server success reports `SUCCEEDED`
- goal rejection reports `REJECTED`
- aborted result reports `ABORTED`
- missing server makes `server_ready()==false` and `send_goal()==false`

- [ ] **Step 2: Run focused test and verify RED**

Expected: missing `HomeActionClient`.

- [ ] **Step 3: Implement minimal action transport**

Build one `trajectory_msgs::msg::JointTrajectoryPoint`:
- `positions = plan.target_radians`
- `time_from_start` from `plan.duration_seconds`
- `trajectory.joint_names = plan.joint_names`

Do not send Cartesian commands and do not own the teleop state machine.

- [ ] **Step 4: Run the synthetic action integration test and verify GREEN**

Expected: all transport scenarios pass without RM driver.

- [ ] **Step 5: Commit**

```bash
git add src/rm65_teleop_adapter/include/rm65_teleop_adapter/home_action_client.hpp         src/rm65_teleop_adapter/src/home_action_client.cpp         src/rm65_teleop_adapter/test/test_home_action_client.cpp         src/rm65_teleop_adapter/CMakeLists.txt         src/rm65_teleop_adapter/package.xml
git commit -m "feat: add right-arm Home action transport"
```

---

### Task 5: Integrate Home into the production adapter node with hardware-only output gating

**Files:**
- Modify: `src/rm65_teleop_adapter/src/adapter_node.cpp`
- Modify: `src/rm65_teleop_adapter/config/hardware.yaml`
- Modify: `src/rm65_teleop_adapter/config/dry_run.yaml`
- Modify: `src/rm65_teleop_adapter/test/test_adapter_config.cpp`
- Modify: `src/rm65_teleop_adapter/test/test_motion_profiles.py`

**Interfaces:**
- New ROS parameters:
  - `home_enabled`
  - `home_button_field`
  - `home_hold_seconds`
  - `home_speed_deg_s`
  - `home_joint_degrees`
  - `home_joint_names`
  - `home_action_name`
  - `joint_state_topic`
  - `joint_state_timeout`
- New input subscription: configured `sensor_msgs/msg/JointState`.
- In hardware mode with Home enabled: create `HomeActionClient`.
- In dry-run: `home_enabled=false`; never create/send a client to the real Home action path.

- [ ] **Step 1: Write config/gating RED tests**

Add tests that assert:
- hardware config contains the temporary six-joint target, 15 deg/s, 1.5 s, verified B field, six verified joint names, real action path
- dry-run config has `home_enabled: false`
- orientation/translation motion profiles contain none of the Home keys
- invalid Home target length, invalid speed/hold, invalid/unknown button field, or invalid joint-name list rejects enabled Home configuration
- `home_enabled=false` permits dry-run to start without an action server.

- [ ] **Step 2: Run config tests and verify RED**

Expected: missing Home parameters / validation.

- [ ] **Step 3: Integrate subscriptions and cached inputs**

In `adapter_node.cpp`:
- parse the verified `home_button_field`
- subscribe to configured `joint_state_topic`
- on each JointState callback, reorder by configured names with Task 2 helper
- only replace cached current joint positions when the full mapping is valid
- maintain `joint_state_received_`, `joint_state_valid_`, and steady timestamp
- read physical B via `quest_face_button_pressed()` in the existing Quest inputs callback
- keep existing Grip `press_middle` code unchanged.

- [ ] **Step 4: Wire Home action readiness/events into each control cycle**

Before `logic_->update(input)`:
- fill Home button state
- joint freshness/validity
- `home_action_ready`
- `home_plan_valid`
- consume exactly one queued `HomeActionEvent`

After `logic_->update(input)`:
- if `home_goal_requested`, build plan from the latest mapped joints and send exactly one action goal
- if send fails despite the precheck, queue `REJECTED` for the next cycle and publish stop
- if `home_cancel_requested`, call `request_cancel()` and `publish_stop()`
- while state is `HOMING`, never publish a Cartesian preview as a hardware command and never publish `movep_canfd_cmd`
- preview publication remains tied only to actual `output.command`.

- [ ] **Step 5: Add shutdown behavior**

If Home is active/pending at node destruction:
- request action cancel
- call existing `publish_stop()`
- do not wait indefinitely in the destructor.

Keep existing ACTIVE destructor stop behavior.

- [ ] **Step 6: Run adapter/config/motion-profile tests GREEN**

Expected:
- all config tests pass
- motion profile allowlist unchanged
- all existing translation/orientation tests remain green.

- [ ] **Step 7: Commit**

```bash
git add src/rm65_teleop_adapter/src/adapter_node.cpp         src/rm65_teleop_adapter/config/hardware.yaml         src/rm65_teleop_adapter/config/dry_run.yaml         src/rm65_teleop_adapter/test/test_adapter_config.cpp         src/rm65_teleop_adapter/test/test_motion_profiles.py
git commit -m "feat: integrate hold-to-run Home control"
```

---

### Task 6: Add watchdog/Home observability without changing thresholds

**Files:**
- Modify: `src/rm65_teleop_adapter/src/adapter_node.cpp`
- Modify: `src/rm65_teleop_adapter/scripts/teleop_status_logic.py`
- Modify: `src/rm65_teleop_adapter/scripts/teleop_status_monitor.py`
- Modify: `src/rm65_teleop_adapter/test/test_teleop_status_logic.py`
- Modify: `src/rm65_teleop_adapter/package.xml`

**Interfaces:**
- Extend adapter JSON with:
  - `quest_pose_age_ms`
  - `inputs_age_ms`
  - `robot_age_ms`
  - `joint_state_age_ms`
  - `rearm_count`
  - `watchdog_count`
  - `home_button_pressed`
  - `home_hold_progress`
  - `home_action_state`
  - existing `state`, `reason`, `command_path_ready` retained.
- Status monitor adds a read-only `/right/joint_states` stream and renders `JOINTS=OK|LOST` plus concise Home state when available.

- [ ] **Step 1: Write RED Python status tests**

Add exact expectations for:
- `JOINTS=LOST` before first joint state
- `JOINTS=OK` after mark
- HOMING line including `HOME=ACTIVE`
- ARMED with B hold progress including a concise `HOME=HOLD(50%)`
- stale/malformed adapter JSON remains backward-safe
- existing deadman fallback behavior remains unchanged.

- [ ] **Step 2: Run pytest and verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /usr/bin/python3 -m pytest   src/rm65_teleop_adapter/test/test_teleop_status_logic.py -q
```

Expected: failures for new joint/Home fields.

- [ ] **Step 3: Implement node-side ages and counters**

Use `SteadyClock`; do not use ROS message stamps for freshness age.

Rules:
- age before first sample = `-1.0`
- increment `rearm_count` once per transition into `REARM_REQUIRED`
- increment `watchdog_count` once per transition caused by existing `input_not_fresh` or any `home_*_not_fresh` reason
- no timeout values are changed.

- [ ] **Step 4: Implement monitor rendering and joint subscription**

Add `sensor_msgs/msg/JointState` read-only subscription and preserve one-line heartbeat behavior.

- [ ] **Step 5: Run Python status tests and adapter regression GREEN**

Expected: new tests pass and old status lines remain compatible except for intentionally appended fields.

- [ ] **Step 6: Commit**

```bash
git add src/rm65_teleop_adapter/src/adapter_node.cpp         src/rm65_teleop_adapter/scripts/teleop_status_logic.py         src/rm65_teleop_adapter/scripts/teleop_status_monitor.py         src/rm65_teleop_adapter/test/test_teleop_status_logic.py         src/rm65_teleop_adapter/package.xml
git commit -m "feat: expose Home and watchdog diagnostics"
```

---

### Task 7: Full regression, isolated synthetic Home exercise, and factual documentation

**Files:**
- Create: `src/rm65_teleop_adapter/test/home_synthetic_probe.py`
- Modify: `src/rm65_teleop_adapter/CMakeLists.txt`
- Modify: `src/rm65_teleop_adapter/README.md`
- Modify: `docs/INTERFACE.md`
- Modify: `STATUS.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/progress/right-arm-recenter-home.md`

**Interfaces:**
- The synthetic probe uses test-only topics/action names and no RM driver.
- Production dry-run remains Home-output-disabled.
- Documentation must distinguish automated/synthetic evidence from later real-RM65 Home validation.

- [ ] **Step 1: Write the synthetic probe before claiming completion**

Probe phases:
1. start with fresh synthetic Quest pose/inputs/robot pose/joint state and synthetic FollowJointTrajectory server under a test-only action name
2. verify B hold `<1.5 s` creates no goal
3. verify threshold crossing creates exactly one Home goal
4. while Home is active, inject Quest translation/rotation and assert zero Cartesian hardware command output
5. release B; verify cancel request reaches synthetic server and state stays HOMING until canceled result
6. verify terminal canceled -> `REARM_REQUIRED`
7. rearm, hold B again, let synthetic server succeed -> `REARM_REQUIRED`
8. repeat with one watchdog stale event -> cancel + no auto-resume
9. assert no process or test action server remains after cleanup.

- [ ] **Step 2: Register/run the synthetic probe and verify GREEN**

Use an isolated domain, for example:

```bash
export ROS_DOMAIN_ID=143
export ROS_LOCALHOST_ONLY=1
```

No RM driver or competition launch is permitted.

- [ ] **Step 3: Run the complete four-package build/test suite**

```bash
/usr/bin/colcon --log-base log build   --build-base build --install-base install --symlink-install   --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter

/usr/bin/colcon --log-base log test   --build-base build --install-base install   --packages-select quest2ros ros_tcp_endpoint q2r2_bringup rm65_teleop_adapter   --event-handlers console_direct+

/usr/bin/colcon test-result --test-result-base build --all --verbose
```

Expected: zero errors/failures.

- [ ] **Step 4: Explicitly inspect unchanged safety-critical behavior**

Verify by diff/test:
- Quest translation bridge production logic unchanged
- quaternion/orientation math unchanged unless a test-required mechanical include/refactor occurred
- `safe/normal/fast` motion profile values unchanged
- deadman thresholds remain 0.60/0.40
- Home keys are not present in motion profiles
- no second Cartesian command publisher exists.

- [ ] **Step 5: Update docs with only observed evidence**

Document:
- measured A/B mapping
- measured six right joint names
- Home state/action contract
- temporary Home target and 15 deg/s
- automated test counts from actual output
- synthetic action/cancel evidence
- explicitly state real RM65 Home is still pending until manually tested.

Do not claim real Home success before the operator performs it.

- [ ] **Step 6: Whole-branch code review before hardware**

Review the branch against the merge base with specific attention to:
- cancel acknowledgement race
- continuous B retrigger
- action callback/event consumption
- joint name mapping
- dry-run action isolation
- single Cartesian command path
- shutdown cancellation
- existing translation/orientation regressions.

Fix every Critical/Important issue with RED -> GREEN evidence before proceeding.

- [ ] **Step 7: Commit and push**

```bash
git add src/rm65_teleop_adapter/test/home_synthetic_probe.py         src/rm65_teleop_adapter/CMakeLists.txt         src/rm65_teleop_adapter/README.md         docs/INTERFACE.md STATUS.md CHANGELOG.md         docs/progress/right-arm-recenter-home.md
git commit -m "docs: complete Home implementation validation"
git push -u origin feat/recenter-home
```

---

## Manual hardware gate after Task 7

This gate is not part of automated completion and must not be represented as already passed.

1. Clear the right-arm workspace; use the already verified right-only RM65 driver/control stack.
2. Confirm the physical B field and six joint names still match recorded evidence.
3. Confirm Grip is released and adapter state is `ARMED`.
4. Start from a posture reasonably near the temporary Home target.
5. Hold B for 1.5 s and confirm a slow joint-space move begins at the configured 15 deg/s nominal envelope.
6. During one test, release B mid-motion and confirm cancel/stop; do not proceed if motion continues unexpectedly.
7. Re-establish `ARMED`, hold B continuously, and allow a complete Home.
8. Confirm success ends in `REARM_REQUIRED`.
9. Confirm holding/pressing Grip during HOMING never creates Cartesian motion.
10. Confirm normal release -> Grip press is required before teleoperation resumes.
11. Record actual result and any target-posture tuning separately; changing the temporary Home joint values must require only config changes, not code changes.
