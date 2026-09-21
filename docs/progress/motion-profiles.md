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
| `normal` | 0.5 | 0.020 | 0.00010 | 0.10 | Implemented; pending real-hardware feel validation |
| `fast` | 0.5 | 0.040 | 0.00020 | 0.10 | Implemented / unvalidated on real hardware |

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

This change has not been tested on a real arm. `normal` is the first candidate
for the next onsite feel-validation round. `fast` is implemented but remains
unvalidated on real hardware; it is not verified or recommended.

## Pending onsite test record

For each candidate profile, record:

| Item | Result |
|---|---|
| Direction | Pending |
| Feel | Pending |
| Deadman stop | Pending |
| Stopping margin | Pending |
| Fault behavior | Pending |
| Final conclusion | Pending |
