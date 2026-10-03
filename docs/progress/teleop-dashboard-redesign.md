# Light workstation visual redesign

## Scope

Continues `feat/teleop-dashboard` from
`4a9be3a353dc1fc9881d08f99d610a16a3dcb5fe`. This revision changes presentation
only. The existing main baseline, ROS interfaces, control stack and hardware
bringup are not altered. No robot or hand hardware is started.

`models.py`, `ros_monitor.py` and `demo_data.py` are unchanged. A regression test
checks their normalized source SHA256 against the above baseline. The existing
13 subscriptions, strict parsers, SnapshotStore, event generation, executor
lifecycle, 10 Hz refresh, demo generation and screenshot shutdown are retained.
Read-only static checks now recurse into the new `pages/` package; the existing
real-rclpy test still verifies 13 subscriptions and zero output endpoints.

## Visual system

- A quiet light theme: `#F5F5F7` canvas, white surfaces, `#1D1D1F` text,
  restrained gray labels and very light dividers.
- A 230 px sidebar and 62 px toolbar replace the three-column overview.
  One selected page occupies the workspace. Toolbar shows the real ROS domain,
  adapter-derived mode, aggregate state, small demo label, READ ONLY and HH:mm.
- Six pages use one surface per semantic group. State text stays neutral with
  small colored dots. Blue is reserved for selected navigation, thin data tracks
  and pressed controller indicators; a pressed button is not an alarm.
- System typography: Microsoft YaHei UI on Windows, Noto Sans CJK SC on Linux,
  Apple system font on macOS, DejaVu Sans fallback. No downloaded fonts, icon
  libraries, Apple assets, gradients, glow, CAD grid or embedded 3D runtime.
- The original QPainter illustration uses six joints per arm, gray links and a
  simple shared base. Its tooltip identifies it as a schematic, not kinematics.
- Typography, spacing and 16 px surface corners establish hierarchy. Animation
  and shadows are intentionally omitted so rendering stays stable and readable.

## Pages and progressive disclosure

| Page / CLI key | Content |
|---|---|
| 总览 / `overview` | Hero schematic, arm states, Quest/ROS/hand health, four metrics, current diagnostics |
| 双臂 / `arms` | Left/right segmented selection; TCP, RPY, six joints, stream ages, deadman and paths; quaternion and target bridge details can be expanded |
| VR 控制器 / `controllers` | Both poses, frequencies/ages, grip/index, X/Y and A/B, existing read-only mappings |
| 安全 / `safety` | Two settings lists for adapter state, paths, counts, cycle, Home and presets; all remaining adapter flags/ages in diagnostic disclosure |
| 灵巧手 / `linkerhand` | Right L7 state, communication/input health, seven target/actual channels, faults only when present, trigger/connection details |
| 事件 / `events` | Light table, 44 px rows, All/Info/Warnings/Errors filters; existing bounded event data is unchanged |

All pages consume `SystemSnapshot`. Hidden pages receive every new snapshot, so
navigation does not resurrect old values. Stale/invalid adapter status cannot
appear as Ready; stale controller buttons do not remain pressed; stale hand
channels show unavailable values. Historical pose/joint observations retain
their explicit stream-health context, as in the previous version.

Overview reports the lower of the two fresh Quest pose rates and the lower of
the two fresh robot feedback rates, the sum of the two known watchdog counts,
and the larger of the two known maximum cycle periods. Missing either input
produces an unavailable metric. Per-side timing and node-count details are
available through hover text and the detailed pages; aggregate status uses the
unchanged model function.

## Files

- Reworked `main_window.py`, `widgets.py`, `styles.py`.
- Added `navigation.py`, Qt-free `view_config.py`, and six modules under `pages/`.
- `app.py` only adds argument parsing for `--page` and selects that initial page.
  `setup.py` installs the new page subpackage.
- Existing seven Qt smoke cases now use the page hierarchy while preserving
  their original startup, four sizes, stale suppression and filtering checks.
  Pure model/parser/demo tests are unchanged.
- Added navigation, six-page offscreen CLI capture, invalid CLI selection,
  hidden-page refresh, long diagnostics, controller stale-input and source
  boundary checks. No pixel comparison is used.
- CI captures all six desktop pages plus a 1366 × 768 overview and the normal
  installed ROS entry point in an isolated offline domain.

## Run and capture

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 run rm65_teleop_dashboard teleop_dashboard --demo --page overview

QT_QPA_PLATFORM=offscreen \
PYTHONPATH=src/rm65_teleop_dashboard \
/usr/bin/python3 -m rm65_teleop_dashboard.app \
  --demo --page arms --screenshot /tmp/arms.png
```

The default page is `overview`. Invalid page names exit with argparse status 2
before Qt or ROS starts. Existing `--demo`, `--screenshot`, width/height and ROS
arguments retain their behavior. Navigation/segments/disclosure are local view
controls and grant no robot command capability.

## Visual review and screenshots

All seven requested captures were generated from the running application and
reviewed individually before push. The first review identified a missing-font
check glyph and an over-tall demo label; the glyph was removed and the toolbar
label aligned to its natural height. Event column headers were aligned with
their values. No overlapping cards, clipped Chinese titles, persistent bright
status blocks or nested surfaces were observed. Smaller detailed pages scroll
vertically; the 1366 overview fits without scrolling.

- [Overview 1920 × 1080](../screenshots/apple-style/overview-1920x1080.png)
- [Arms 1920 × 1080](../screenshots/apple-style/arms-1920x1080.png)
- [Controllers 1920 × 1080](../screenshots/apple-style/controllers-1920x1080.png)
- [Safety 1920 × 1080](../screenshots/apple-style/safety-1920x1080.png)
- [LinkerHand 1920 × 1080](../screenshots/apple-style/linkerhand-1920x1080.png)
- [Events 1920 × 1080](../screenshots/apple-style/events-1920x1080.png)
- [Overview 1366 × 768](../screenshots/apple-style/overview-1366x768.png)

## Validation record

Windows isolated Python / PyQt5: **49 passed, 1 skipped, 4 subtests passed**.
The skipped case requires ROS; the six CLI screenshot subprocesses all passed.
Windows restricted pytest temporary-directory ACLs required the validation run
to have access to its own temporary output directory; no application change or
dependency/environment change was needed.

Ubuntu 22.04 / Humble validation uses the existing branch CI: system Python
3.10, system PyQt5, five-package build/test, the real 13-topic receive probe and
the normal ROS-mode offline entry point. The unchanged baseline exclusion of
three onsite `test_right_linkerhand_transport` cases remains necessary because
their unversioned external SDK is unavailable in CI. This revision does not
claim onsite hardware or SDK validation.

Verified on 2026-10-03 against application commit
`2fd724213ae483f2a46a014e19f17bc056ba2317`. Both the push and PR runs succeeded;
the detailed figures below come from
[PR CI run 36998296472](https://github.com/Kiklyyy/quest-rm65-teleop/actions/runs/36998296472).

| Check | Verified result |
|---|---|
| Runtime | Ubuntu 22.04 / ROS 2 Humble / system Python 3.10.12 / system PyQt5 |
| Five-package build | Passed, 39.4 s |
| Dashboard-selected build | Passed, 1.33 s |
| Dashboard tests | 50 passed, 0 skipped, 10.83 s |
| Five-package software regression | 318 reported tests, 0 errors, 0 failures, 0 skipped, 28.6 s |
| Adapter CTest groups | 19/19 passed; the three onsite SDK cases remain excluded as documented above |
| Actual ROS receive probe | 13 subscriptions, shuffled six-joint ordering, 72/198 Hz receipt, malformed JSON, stale suppression and deduplicated events passed |
| Output endpoints and shutdown | Zero publishers/services/clients on the monitor; executor/thread/context clean shutdown passed |
| Screenshots | All six 1920 × 1080 pages and 1366 × 768 overview captured on Ubuntu; installed normal ROS-mode offline entry point also captured and exited |

Ubuntu-rendered captures were additionally reviewed for system-font differences,
Chinese text and layout. The committed Windows captures and the Linux CI
artifacts both preserve the intended light visual hierarchy. No new runtime
code changes were needed after validation. PR: [#10](https://github.com/Kiklyyy/quest-rm65-teleop/pull/10).
