from enum import Enum, auto
from math import isfinite


Position = tuple[float, float, float]


class BridgeState(Enum):
    INACTIVE = auto()
    ACTIVE = auto()
    REARM_REQUIRED = auto()


class QuestRightTargetLogic:
    def __init__(
        self,
        initial_target: Position = (0.5, 0.0, 0.5),
        scale: float = 1.0,
        timeout_s: float = 0.2,
    ) -> None:
        self._target = self._as_position(initial_target)
        self._scale = float(scale)
        self._timeout_s = float(timeout_s)
        self._state = BridgeState.INACTIVE

        self._latest_pose = None
        self._last_pose_time = None
        self._anchor_pose = None
        self._anchor_target = None

        self._deadman_pressed = False
        self._activation_pending = False
        self._pending_since = None
        self._last_accepted_time = float("-inf")

    @staticmethod
    def _as_position(position: Position) -> Position:
        x, y, z = position
        return (float(x), float(y), float(z))

    def _accept_time(self, now_s: float):
        now = float(now_s)
        if not isfinite(now) or now < self._last_accepted_time:
            return None
        self._last_accepted_time = now
        return now

    def _age(self, now_s: float, reference_s: float) -> float:
        return max(0.0, now_s - reference_s)

    def _activate(self, pose: Position) -> None:
        self._anchor_pose = pose
        self._anchor_target = self._target
        self._activation_pending = False
        self._pending_since = None
        self._state = BridgeState.ACTIVE

    def _enter_rearm_required(self) -> None:
        self._state = BridgeState.REARM_REQUIRED
        self._activation_pending = False
        self._pending_since = None
        self._anchor_pose = None
        self._anchor_target = None

    def update_pose(self, position: Position, now_s: float) -> None:
        now = self._accept_time(now_s)
        if now is None:
            return

        pose = self._as_position(position)
        previous_pose_time = self._last_pose_time
        self._latest_pose = pose
        self._last_pose_time = now

        if self._state is BridgeState.ACTIVE:
            if (
                previous_pose_time is not None
                and self._age(now, previous_pose_time) > self._timeout_s
            ):
                self._enter_rearm_required()
                return

            self._target = tuple(
                self._anchor_target[index]
                + self._scale * (pose[index] - self._anchor_pose[index])
                for index in range(3)
            )
            return

        if self._activation_pending and self._deadman_pressed:
            if self._age(now, self._pending_since) > self._timeout_s:
                self._enter_rearm_required()
                return
            self._activate(pose)

    def update_deadman(self, pressed: bool, now_s: float) -> None:
        pressed = bool(pressed)
        if not pressed:
            now = float(now_s)
            if isfinite(now) and now > self._last_accepted_time:
                self._last_accepted_time = now
            self._deadman_pressed = False
            self._state = BridgeState.INACTIVE
            self._activation_pending = False
            self._pending_since = None
            self._anchor_pose = None
            self._anchor_target = None
            return

        now = self._accept_time(now_s)
        if now is None:
            return

        if self._deadman_pressed:
            return

        self._deadman_pressed = True

        if self._state is BridgeState.REARM_REQUIRED:
            return

        pose_is_fresh = (
            self._latest_pose is not None
            and self._last_pose_time is not None
            and self._age(now, self._last_pose_time) <= self._timeout_s
        )

        if pose_is_fresh:
            self._activate(self._latest_pose)
            return

        self._state = BridgeState.INACTIVE
        self._activation_pending = True
        self._pending_since = now

    def check_timeout(self, now_s: float) -> None:
        now = self._accept_time(now_s)
        if now is None:
            return

        if (
            self._state is BridgeState.ACTIVE
            and self._last_pose_time is not None
            and self._age(now, self._last_pose_time) > self._timeout_s
        ):
            self._enter_rearm_required()
            return

        if (
            self._activation_pending
            and self._pending_since is not None
            and self._age(now, self._pending_since) > self._timeout_s
        ):
            self._enter_rearm_required()

    @property
    def target(self) -> Position:
        return self._target

    @property
    def state(self) -> BridgeState:
        return self._state

    @property
    def activation_pending(self) -> bool:
        return self._activation_pending
