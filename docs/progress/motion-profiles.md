# Motion profiles progress

## Git state

- Branch: `feat/motion-profiles`
- Base: `origin/main` at `75939d640c38a2ccd2275645fd1ab3e8ef98401e`
- Implementation checkpoint: `ac2f9bd` (`feat: add teleop motion profile selection`)

## Design

`hardware.yaml` remains the hardware safety base. Hardware mode loads the base
first and one versioned motion profile second. Profiles may contain only:

- `translation_scale`
- `max_velocity_mps`
- `max_step_m`
- `max_anchor_distance_m`

The default is always `safe`. Invalid profile names fail launch. Dry-run ignores
the profile override for adapter parameters and never enables hardware output.

## Profiles

| Profile | translation_scale | max_velocity_mps | max_step_m | max_anchor_distance_m | Hardware status |
|---|---:|---:|---:|---:|---|
| `safe` | 0.2 | 0.005 | 0.00005 | 0.03 | Existing real-hardware baseline parameters |
| `normal` | 1.0 | 0.20 | 0.00050 | 1.0 | Real Quest → right RM65 feel-tested tuning value |
| `fast` | 0.5 | 0.040 | 0.00020 | 0.10 | Experimental; not for hardware use yet |

## Automated verification

TDD RED was recorded before implementation: all 9 new tests failed because the
launch argument, parameter-selection helper, invalid-value rejection, and
profile files did not yet exist. After implementation:

- four-package isolated build: passed;
- adapter logic: 12 GTest cases passed;
- status monitor: 8 pytest cases passed;
- motion profiles: 9 pytest cases passed;
- Quest bridge: 56 pytest cases passed with user-site plugin autoload disabled;
- `colcon test-result --all`: 88 reported tests, 0 errors, 0 failures, 0 skipped
  (includes 3 CTest wrapper entries in addition to the 85 functional cases).

## Dry-run smoke

The unified launch was run in isolated ROS domains with TCP, Quest bridge,
status monitor, RViz, and RM driver disabled. For `safe`, `normal`, and `fast`:

- launch started the adapter successfully;
- launch logged `mode=DRY_RUN` and the requested profile;
- adapter parameter `dry_run` remained `true`;
- `/right/rm_driver/movep_canfd_cmd` was absent, so publisher count was 0.

`motion_profile:=turbo` exited with code 1 and reported the allowed values. No
real RM65 driver was started and no robot command was sent.

## Hardware validation state

An onsite operator tested `normal` with a real Quest and the real right RM65
using:

- `translation_scale: 1.0`
- `max_velocity_mps: 0.20`
- `max_step_m: 0.0005`
- `max_anchor_distance_m: 1.0`

The arm followed normally, and the operator reported that the new tuning was
clearly more responsive with a substantially more reasonable translation
range than the previous parameters. The larger `max_step_m` was considered the
most noticeable contributor to the improved feel. XYZ translation through the
full Quest → right RM65 path had already been established and remained
functional during this test.

At the nominal 200 Hz control rate, `max_step_m: 0.0005` gives a theoretical
step-derived upper bound of approximately 0.10 m/s. This is a calculation, not
a measured robot speed, and it means the step limit normally constrains motion
before `max_velocity_mps: 0.20` does.

This test did not systematically measure exact speed, stopping distance,
overshoot, long-duration stability, or the safety boundary of the 1.0 m anchor
radius. `max_anchor_distance_m: 1.0` is a field-tested tuning value pending
workspace and stopping-margin review; it is not a recommended safety boundary.
`fast` remains unvalidated on real hardware and is experimental / not for
hardware use yet.

## Pending onsite test record

For each candidate profile, record:

| Item | Result |
|---|---|
| Direction | Pending |
| Feel | `normal` clearly improved in one real Quest → right RM65 session |
| Deadman stop | Pending |
| Stopping margin | Pending |
| Fault behavior | Pending |
| Long-duration stability | Pending |
| Final safety conclusion | Pending |
