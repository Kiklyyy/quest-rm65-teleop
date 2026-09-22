#!/usr/bin/env python3

import json
from typing import Dict, Optional


STREAM_NAMES = ("quest", "inputs", "target", "robot")


class TeleopStatusModel:
    """Display-only freshness and adapter-status aggregation."""

    def __init__(
        self,
        stream_timeout_s: float = 0.5,
        adapter_timeout_s: float = 0.5,
        heartbeat_s: float = 1.0,
    ) -> None:
        self._stream_timeout_s = stream_timeout_s
        self._adapter_timeout_s = adapter_timeout_s
        self._heartbeat_s = heartbeat_s
        self._stream_times: Dict[str, Optional[float]] = {
            name: None for name in STREAM_NAMES
        }
        self._adapter_time: Optional[float] = None
        self._adapter = self._unknown_adapter()
        self._last_line: Optional[str] = None
        self._last_emit_time: Optional[float] = None

    @staticmethod
    def _unknown_adapter() -> dict:
        return {
            "state": "UNKNOWN",
            "deadman": "?",
            "command": "UNKNOWN",
            "reason": "",
        }

    def mark_stream(self, name: str, now_s: float) -> None:
        if name not in self._stream_times:
            raise ValueError(f"unknown stream: {name}")
        self._stream_times[name] = now_s

    def update_adapter(self, payload: str, now_s: float) -> None:
        self._adapter_time = now_s
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            self._adapter = self._unknown_adapter()
            return
        if not isinstance(decoded, dict):
            self._adapter = self._unknown_adapter()
            return

        state = decoded.get("state")
        deadman_pressed = decoded.get("deadman_pressed")
        if not isinstance(deadman_pressed, bool):
            deadman_pressed = decoded.get("button_lower")
        command_path_ready = decoded.get("command_path_ready")
        reason = decoded.get("reason")
        self._adapter = {
            "state": state if isinstance(state, str) and state else "UNKNOWN",
            "deadman": (
                "ON" if deadman_pressed is True else
                "OFF" if deadman_pressed is False else "?"
            ),
            "command": (
                "OK" if command_path_ready is True else
                "BLOCKED" if command_path_ready is False else "UNKNOWN"
            ),
            "reason": reason if isinstance(reason, str) else "",
        }

    @staticmethod
    def _is_fresh(last_seen_s: Optional[float], now_s: float, timeout_s: float) -> bool:
        return last_seen_s is not None and 0.0 <= now_s - last_seen_s <= timeout_s

    def render(self, now_s: float) -> str:
        freshness = {
            name: "OK" if self._is_fresh(stamp, now_s, self._stream_timeout_s) else "LOST"
            for name, stamp in self._stream_times.items()
        }
        adapter = self._adapter
        if not self._is_fresh(self._adapter_time, now_s, self._adapter_timeout_s):
            adapter = self._unknown_adapter()

        line = (
            f"[teleop] QUEST={freshness['quest']} INPUTS={freshness['inputs']} "
            f"TARGET={freshness['target']} ROBOT={freshness['robot']} "
            f"STATE={adapter['state']} DEADMAN={adapter['deadman']} "
            f"CMD={adapter['command']}"
        )
        reason = "_".join(adapter["reason"].split())
        if reason:
            line += f" REASON={reason}"
        return line

    def take_line_if_due(self, now_s: float) -> Optional[str]:
        line = self.render(now_s)
        changed = line != self._last_line
        heartbeat_due = (
            self._last_emit_time is None or
            now_s - self._last_emit_time >= self._heartbeat_s
        )
        if not changed and not heartbeat_due:
            return None
        self._last_line = line
        self._last_emit_time = now_s
        return line
