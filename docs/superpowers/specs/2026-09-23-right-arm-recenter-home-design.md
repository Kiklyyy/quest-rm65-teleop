# Right-arm Recenter, Home, and Stability Design

Date: 2026-09-23  
Branch: `feat/recenter-home`  
Base: `main`

## 1. Purpose

The right-arm Quest teleoperation stack already supports validated relative XYZ + orientation control with a middle-finger Grip deadman. This change adds a safe right-arm Home operation and closes several observability gaps around watchdog/rearm behavior.

The design must preserve one-control-source-at-a-time semantics. Cartesian Quest teleoperation and joint-space Home motion must never command the arm concurrently.

## 2. Agreed operator controls

- Middle-finger Grip remains the teleoperation deadman.
- The Quest A button is reserved for Recenter behavior.
- The Quest B button is used for Home.
- A/B must not be bound to `button_upper` or `button_lower` by assumption. A short live Quest input probe must establish the physical mapping before implementation locks the binding.
- Home requires B to be held continuously. A B hold shorter than 1.5 s does not start Home.
- Home can start only while Grip is released and the adapter is in `ARMED`.

## 3. Recenter design decision

The existing control architecture already captures fresh Quest position/orientation and robot position/orientation anchors on every released -> Grip-pressed transition. Therefore a second manual anchor capture while already `ARMED` would be overwritten at the next Grip press and would have no motion effect.

To avoid adding a misleading no-op control, this change does **not** create a second independent anchor path. The existing Grip press remains the actual recenter/re-anchor operation for motion control.

The A button remains reserved in the interface contract. During this feature implementation, a live probe identifies its input field and tests may cover its reservation, but A does not alter robot state or bypass the existing Grip re-anchor semantics.

If a later operator workflow needs an ACTIVE-session recenter/freeze gesture, that is a separate behavior change and requires a new design because it changes motion authorization semantics.

## 4. Temporary Home target

The current Home target is provisional and intended to change later when the tool-holding posture is finalized.

Temporary right RM65 target in degrees:

```text
J1 = -95.605
J2 =   4.406
J3 = -80.034
J4 = -22.695
J5 = -48.462
J6 =  97.570
```

The values must be configuration, not production-code constants.

Suggested configuration contract:

```yaml
home_joint_degrees: [-95.605, 4.406, -80.034, -22.695, -48.462, 97.570]
home_speed_deg_s: 15.0
home_hold_seconds: 1.5
```

All six Home joint values and Home timing/speed parameters must be finite and validated at startup.

## 5. Home command path

Home uses the existing right-arm FollowJointTrajectory action:

```text
/right/rm_group_controller/follow_joint_trajectory
```

Home does not use Cartesian `movep_canfd_cmd`.

The implementation uses the right-arm joint names from the established right-arm interface / `/right/joint_states` ordering and converts configured degrees to radians before building the trajectory.

The nominal trajectory duration is based on the farthest joint displacement:

```text
max_delta_deg = max_i(abs(home_i - current_i))
duration_s = max_delta_deg / home_speed_deg_s
```

The implementation may enforce a small positive minimum duration for numerically valid near-Home requests, but it must not create a trajectory whose nominal average joint speed exceeds `home_speed_deg_s`.

No MoveIt/CuRobo planning or collision checking is added in this feature. The configured Home posture is therefore a validated operator target, not a collision-free planning guarantee.

## 6. State machine

Existing states remain:

```text
DISABLED
ARMED
ACTIVE
REARM_REQUIRED
FAULT
```

Add:

```text
HOMING
```

### 6.1 Entering HOMING

HOMING may start only when all of the following are true:

- current state is `ARMED`
- Grip deadman is released
- physical B button has been held continuously for at least 1.5 s
- Quest pose, Quest inputs, robot feedback, and joint-state inputs are fresh
- Home configuration is valid
- FollowJointTrajectory action server is available
- there is no active Cartesian teleoperation command session
- there is no existing Home goal in flight

If any precondition is missing, Home does not start.

### 6.2 During HOMING

While `HOMING`:

- no Cartesian pose command is emitted by the teleop path
- A is ignored
- Grip press does not re-enter `ACTIVE`
- B must remain held
- Quest pose, Quest inputs, robot feedback, and joint-state watchdogs remain active
- action feedback/result is monitored
- only one Home goal may exist

### 6.3 Home cancellation

The Home trajectory is canceled if any of these occurs:

- B is released
- a required watchdog becomes stale
- FollowJointTrajectory reports abort/reject/failure
- robot/joint feedback becomes invalid
- node shutdown occurs while Home is active
- an internal arbitration invariant is violated

Cancellation requests the action cancel first and also uses the existing right-arm stop path where appropriate so the arm is not left executing a stale trajectory.

A canceled or failed Home must not automatically resume teleoperation.

### 6.4 Home completion

Successful Home completion transitions to:

```text
REARM_REQUIRED
```

The operator must return to the normal release -> Grip press authorization flow before Cartesian teleoperation can become `ACTIVE` again.

There is no automatic transition from Home completion directly into teleoperation.

## 7. Control arbitration

The adapter is the single authority deciding whether the right arm is in Cartesian teleoperation or joint-space Home mode.

The invariant is:

```text
ACTIVE  -> Cartesian streaming allowed, Home goal forbidden
HOMING  -> Home goal allowed, Cartesian streaming forbidden
all other states -> neither motion source may actively stream
```

The Home action client must not be implemented as an independent node that can command the arm without consulting the teleop state machine.

Entering Home is only possible from `ARMED`, so there is no need to switch directly from a live Cartesian stream to a joint trajectory.

## 8. Input mapping probe

Before the A/B binding is committed, use the real Quest in a no-motion/dry-run context and observe `/q2r_right_hand_inputs`.

The probe must determine which physical button changes:

- `button_upper`
- `button_lower`

for physical A and B.

The result is documented and covered by tests. If the physical mapping is ambiguous, implementation stops rather than guessing.

The existing Grip mapping to `press_middle` is unchanged.

## 9. Stability and observability closeout

This feature does not loosen watchdog thresholds or motion limits.

Status/diagnostic output is extended so a later field issue can identify which input became stale and what control mode was active. At minimum expose:

- control mode / state: idle, teleop-active, homing, rearm, fault
- Quest pose age
- Quest inputs age
- robot pose age
- joint-state age
- last rearm/fault reason
- cumulative watchdog/rearm count
- Home hold progress or armed/not-armed state
- Home action state/result when relevant
- command-path readiness

These additions are observational only and do not bypass existing safety gates.

## 10. Safety behavior

The following rules are mandatory:

- Home cannot start from `ACTIVE`.
- Home cannot start while Grip is pressed.
- B must remain pressed for the entire Home motion.
- Releasing B cancels Home.
- Watchdog loss cancels Home.
- A has no motion authority during Home.
- Grip has no motion authority during Home.
- Home completion does not auto-resume teleoperation.
- Invalid Home joint values reject startup or Home initiation.
- Missing FollowJointTrajectory server prevents Home initiation.
- Cartesian teleop and Home trajectory must never command simultaneously.
- Existing `move_stop_cmd`, teleop deadman, rearm, fault, mapping, workspace and orientation safety behavior remain unchanged outside the explicit Home state.

## 11. Testing strategy

Implementation is test-driven.

### 11.1 Pure/state-machine tests

Cover at least:

- B hold shorter than 1.5 s does not start Home
- exactly reaching the hold threshold permits one Home request
- Home starts only from `ARMED`
- Grip pressed blocks Home
- stale Quest pose blocks/cancels Home
- stale Quest inputs block/cancel Home
- stale robot pose blocks/cancels Home
- stale joint states block/cancel Home
- B release during Home requests cancel
- action reject/abort/failure exits Home safely
- successful result enters `REARM_REQUIRED`
- Grip during Home cannot create Cartesian output
- no Cartesian command is produced in `HOMING`
- only one Home goal is issued per continuous B hold
- new Home requires release/re-hold after completion/cancel
- invalid Home configuration is rejected
- trajectory duration respects the configured nominal speed limit

### 11.2 Input binding tests

After the real Quest probe, lock and test the physical A/B -> message-field mapping.

### 11.3 Integration dry-run

Use isolated ROS domain and synthetic joint/pose/input sources.

Verify:

- action client waits for the expected right-arm action server
- Home goal is produced only after the full hold gate
- B release cancels the synthetic action
- watchdog loss cancels the synthetic action
- Home success returns `REARM_REQUIRED`
- `/right/rm_driver/movep_canfd_cmd` receives no teleop command while Home is active
- no real RM driver is required for this test

### 11.4 Real robot gate

Only after automated and dry-run evidence passes:

1. verify physical B mapping
2. verify Home target visually with the arm at low risk / clear workspace
3. start from a nearby posture
4. hold B and confirm slow joint-space return
5. release B mid-motion once and confirm cancellation/stop
6. run a complete Home
7. confirm `REARM_REQUIRED`
8. confirm Grip must be reauthorized before teleoperation resumes

The temporary Home target may be tuned later without code changes.

## 12. Out of scope

This feature does not add:

- gripper control
- left-arm teleoperation
- dual-arm coordination
- MoveIt/CuRobo Home planning
- collision avoidance
- final surgical/tool-holding Home posture
- ACTIVE-session manual Recenter semantics
- automatic Home on startup, disconnect, or fault

## 13. Acceptance criteria

The feature is accepted when:

- physical B mapping is verified rather than assumed
- Home configuration is parameterized
- B hold-to-run Home works through the right FollowJointTrajectory action
- B release/watchdog/action failure cancels safely
- Home and Cartesian teleoperation are mutually exclusive
- Home success ends in `REARM_REQUIRED`
- existing XYZ + orientation teleoperation regressions remain green
- stability/status additions identify stale sources without changing thresholds
- dry-run integration passes before real robot Home testing
- real robot Home and mid-motion B-release cancellation are manually accepted
