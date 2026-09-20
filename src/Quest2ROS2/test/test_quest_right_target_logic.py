import pytest

from q2r2_bringup.quest_right_target_logic import (
    BridgeState,
    QuestRightTargetLogic,
)


INITIAL_TARGET = (0.5, 0.0, 0.5)
ANCHOR_POSE = (1.0, 2.0, 3.0)


def make_active() -> QuestRightTargetLogic:
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=1.0)
    logic.update_deadman(True, now_s=1.0)
    assert logic.state is BridgeState.ACTIVE
    return logic


def test_initial_target():
    logic = QuestRightTargetLogic()

    assert logic.target == pytest.approx(INITIAL_TARGET)
    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is False


def test_inactive_pose_movement_is_ignored():
    logic = QuestRightTargetLogic()

    logic.update_pose((8.0, 9.0, 10.0), now_s=1.0)

    assert logic.target == pytest.approx(INITIAL_TARGET)
    assert logic.state is BridgeState.INACTIVE


def test_first_normal_press_does_not_jump():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=1.0)

    logic.update_deadman(True, now_s=1.1)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_active_x_movement():
    logic = make_active()

    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)

    assert logic.target == pytest.approx((0.6, 0.0, 0.5))


def test_active_y_movement():
    logic = make_active()

    logic.update_pose((1.0, 2.1, 3.0), now_s=1.1)

    assert logic.target == pytest.approx((0.5, 0.1, 0.5))


def test_active_z_movement():
    logic = make_active()

    logic.update_pose((1.0, 2.0, 3.1), now_s=1.1)

    assert logic.target == pytest.approx((0.5, 0.0, 0.6))


def test_active_multi_axis_movement():
    logic = make_active()

    logic.update_pose((1.1, 1.8, 3.3), now_s=1.1)

    assert logic.target == pytest.approx((0.6, -0.2, 0.8))


def test_active_zero_displacement():
    logic = make_active()

    logic.update_pose(ANCHOR_POSE, now_s=1.1)

    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_release_freezes_target():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    frozen = logic.target

    logic.update_deadman(False, now_s=1.2)

    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(frozen)


def test_movement_while_released_is_ignored():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    logic.update_deadman(False, now_s=1.2)
    frozen = logic.target

    logic.update_pose((9.0, 9.0, 9.0), now_s=1.3)

    assert logic.target == pytest.approx(frozen)


def test_repress_reanchors_without_jump():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    logic.update_deadman(False, now_s=1.2)
    frozen = logic.target
    logic.update_pose((5.0, 6.0, 7.0), now_s=1.3)

    logic.update_deadman(True, now_s=1.31)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(frozen)

    logic.update_pose((5.1, 6.0, 7.0), now_s=1.4)
    assert logic.target == pytest.approx(
        (frozen[0] + 0.1, frozen[1], frozen[2])
    )


def test_repeated_true_does_not_reset_anchor():
    logic = make_active()
    original_anchor = logic._anchor_pose
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    target_before_repeat = logic.target

    logic.update_deadman(True, now_s=1.15)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(target_before_repeat)
    assert logic._anchor_pose == original_anchor


def test_repeated_false_is_harmless():
    logic = QuestRightTargetLogic()

    logic.update_deadman(False, now_s=1.0)
    logic.update_deadman(False, now_s=1.1)

    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(INITIAL_TARGET)
    assert logic.activation_pending is False


def test_timeout_at_exact_boundary_does_not_trigger():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)

    logic.check_timeout(now_s=0.2)

    assert logic.state is BridgeState.ACTIVE


def test_timeout_above_boundary_requires_rearm():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)

    logic.check_timeout(now_s=0.200001)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pose_recovery_while_held_stays_rearm_required():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)
    logic.check_timeout(now_s=0.21)

    logic.update_pose((4.0, 5.0, 6.0), now_s=0.22)
    logic.update_deadman(True, now_s=0.23)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_release_from_rearm_required_returns_inactive():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)
    logic.check_timeout(now_s=0.21)

    logic.update_deadman(False, now_s=0.22)

    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_repress_after_rearm_required_activates():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)
    logic.check_timeout(now_s=0.21)
    logic.update_deadman(False, now_s=0.22)
    logic.update_pose((4.0, 5.0, 6.0), now_s=0.23)

    logic.update_deadman(True, now_s=0.24)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_press_before_first_pose_enters_pending_without_jump():
    logic = QuestRightTargetLogic()

    logic.update_deadman(True, now_s=0.0)

    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is True
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_first_pose_after_pending_press_anchors_without_jump():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose(ANCHOR_POSE, now_s=0.1)

    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pending_activation_times_out_and_locks():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.check_timeout(now_s=0.2)
    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is True

    logic.check_timeout(now_s=0.200001)
    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.activation_pending is False


def test_stale_pose_cannot_be_used_as_anchor():
    logic = QuestRightTargetLogic()
    logic.update_pose((9.0, 9.0, 9.0), now_s=0.0)

    logic.update_deadman(True, now_s=0.3)

    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is True
    assert logic.target == pytest.approx(INITIAL_TARGET)

    logic.update_pose(ANCHOR_POSE, now_s=0.4)

    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pending_release_cancels_activation():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_deadman(False, now_s=0.1)
    logic.update_pose(ANCHOR_POSE, now_s=0.15)

    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pending_repeated_true_does_not_extend_deadline():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_deadman(True, now_s=0.19)
    logic.check_timeout(now_s=0.200001)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.activation_pending is False


def test_pending_pose_at_exact_boundary_activates():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose(ANCHOR_POSE, now_s=0.2)

    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_pending_late_pose_itself_locks_without_jump():
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose((9.0, 9.0, 9.0), now_s=0.200001)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_non_monotonic_time_is_ignored():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    stable_target = logic.target
    stable_anchor = logic._anchor_pose

    logic.update_pose((9.0, 9.0, 9.0), now_s=1.05)
    logic.check_timeout(now_s=1.0)
    logic.update_deadman(True, now_s=1.02)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx(stable_target)
    assert logic._anchor_pose == stable_anchor

    logic.update_deadman(False, now_s=0.9)
    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(stable_target)

    logic.update_deadman(True, now_s=1.0)
    assert logic.state is BridgeState.INACTIVE
    assert logic.target == pytest.approx(stable_target)


def test_repeated_identical_pose_does_not_change_target():
    logic = make_active()
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    stable_target = logic.target

    logic.update_pose((1.1, 2.0, 3.0), now_s=1.15)
    logic.update_pose((1.1, 2.0, 3.0), now_s=1.19)

    assert logic.target == pytest.approx(stable_target)


def test_pose_age_at_exact_boundary_is_fresh_for_press():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)

    logic.update_deadman(True, now_s=0.2)

    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_late_pose_itself_locks_before_target_update():
    logic = QuestRightTargetLogic()
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose((9.0, 9.0, 9.0), now_s=0.21)

    assert logic.state is BridgeState.REARM_REQUIRED
    assert logic.target == pytest.approx(INITIAL_TARGET)


def test_non_default_scale_is_applied_per_axis():
    logic = QuestRightTargetLogic(scale=2.0)
    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)

    logic.update_pose((1.1, 1.9, 3.2), now_s=0.1)

    assert logic.target == pytest.approx((0.7, -0.2, 0.9))


def test_custom_initial_target_is_preserved_on_activation():
    logic = QuestRightTargetLogic(initial_target=(1.0, -1.0, 2.0))
    logic.update_pose(ANCHOR_POSE, now_s=0.0)

    logic.update_deadman(True, now_s=0.1)

    assert logic.state is BridgeState.ACTIVE
    assert logic.target == pytest.approx((1.0, -1.0, 2.0))


NON_FINITE_TIMES = (
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="positive-infinity"),
    pytest.param(float("-inf"), id="negative-infinity"),
)


def safety_snapshot(logic: QuestRightTargetLogic):
    return (
        logic.target,
        logic.state,
        logic.activation_pending,
        logic._latest_pose,
        logic._last_pose_time,
        logic._anchor_pose,
        logic._anchor_target,
        logic._pending_since,
        logic._last_accepted_time,
        logic._deadman_pressed,
    )


@pytest.mark.parametrize("non_finite_time", NON_FINITE_TIMES)
def test_nonfinite_initial_events_are_ignored(non_finite_time):
    logic = QuestRightTargetLogic()
    initial = safety_snapshot(logic)

    logic.update_pose((9.0, 9.0, 9.0), now_s=non_finite_time)
    assert safety_snapshot(logic) == initial

    logic.update_deadman(True, now_s=non_finite_time)
    assert safety_snapshot(logic) == initial

    logic.check_timeout(now_s=non_finite_time)
    assert safety_snapshot(logic) == initial

    logic.update_pose(ANCHOR_POSE, now_s=0.0)
    logic.update_deadman(True, now_s=0.0)
    assert logic.state is BridgeState.ACTIVE


@pytest.mark.parametrize("non_finite_time", NON_FINITE_TIMES)
def test_nonfinite_active_pose_update_preserves_state_cache_and_watermark(
    non_finite_time,
):
    logic = make_active()
    active = safety_snapshot(logic)

    logic.update_pose((9.0, 9.0, 9.0), now_s=non_finite_time)

    assert safety_snapshot(logic) == active

    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    assert logic.target == pytest.approx((0.6, 0.0, 0.5))


@pytest.mark.parametrize("non_finite_time", NON_FINITE_TIMES)
def test_nonfinite_pressed_event_preserves_pending_deadline_and_recovery(
    non_finite_time,
):
    logic = QuestRightTargetLogic()
    logic.update_deadman(True, now_s=0.0)
    pending = safety_snapshot(logic)

    logic.update_deadman(True, now_s=non_finite_time)

    assert safety_snapshot(logic) == pending

    logic.update_pose(ANCHOR_POSE, now_s=0.1)
    assert logic.state is BridgeState.ACTIVE
    assert logic.activation_pending is False


@pytest.mark.parametrize("non_finite_time", NON_FINITE_TIMES)
def test_nonfinite_watchdog_preserves_active_state_and_finite_recovery(
    non_finite_time,
):
    logic = make_active()
    active = safety_snapshot(logic)

    logic.check_timeout(now_s=non_finite_time)

    assert safety_snapshot(logic) == active

    logic.update_pose((1.1, 2.0, 3.0), now_s=1.1)
    assert logic.target == pytest.approx((0.6, 0.0, 0.5))


@pytest.mark.parametrize("non_finite_time", NON_FINITE_TIMES)
def test_nonfinite_release_freezes_without_poisoning_finite_rearm(
    non_finite_time,
):
    logic = make_active()
    frozen_target = logic.target
    latest_pose = logic._latest_pose
    last_pose_time = logic._last_pose_time
    last_accepted_time = logic._last_accepted_time

    logic.update_deadman(False, now_s=non_finite_time)

    assert logic.state is BridgeState.INACTIVE
    assert logic.activation_pending is False
    assert logic.target == pytest.approx(frozen_target)
    assert logic._latest_pose == latest_pose
    assert logic._last_pose_time == last_pose_time
    assert logic._anchor_pose is None
    assert logic._anchor_target is None
    assert logic._last_accepted_time == last_accepted_time

    logic.update_pose((4.0, 5.0, 6.0), now_s=1.1)
    logic.update_deadman(True, now_s=1.1)
    assert logic.state is BridgeState.ACTIVE