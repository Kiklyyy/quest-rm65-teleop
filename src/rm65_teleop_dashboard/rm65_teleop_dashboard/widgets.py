"""Reusable display-only cards and vector illustrations. No ROS dependencies."""

import math

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QSizePolicy,
    QVBoxLayout, QWidget,
)

from .styles import COLORS, SECONDARY, TEXT, apply_tone
from .models import status_tone as tone_for


def number(value, decimals=1, suffix=""):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "—"
    return f"{value:.{decimals}f}{suffix}"


def label(text="", role=None, alignment=None):
    result = QLabel(text)
    if role:
        result.setProperty("role", role)
    if alignment is not None:
        result.setAlignment(alignment)
    return result


def pill(text="UNKNOWN"):
    result = label(text, "pill")
    result.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    apply_tone(result, tone_for(text))
    return result


def set_state(widget, text, tone=None):
    widget.setText(str(text))
    apply_tone(widget, tone or tone_for(text))


def age_text(health):
    return number(health.age_ms, 0, " ms") if health.age_ms is not None else "LOST"


def fresh_state(health, state):
    if health.state == "ONLINE":
        return state
    return "LOST" if health.state == "OFFLINE" else health.state


class Card(QFrame):
    def __init__(self, title, subtitle="", parent=None, role="card"):
        super().__init__(parent)
        self.setProperty("role", role)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(12, 10, 12, 11)
        self.body.setSpacing(8)
        self.heading = QHBoxLayout()
        self.heading.setSpacing(7)
        self.heading.addWidget(label(title, "section"))
        self.heading.addStretch()
        self.body.addLayout(self.heading)
        if subtitle:
            subtitle_label = label(subtitle, "secondary")
            subtitle_label.setWordWrap(True)
            self.body.addWidget(subtitle_label)


class ValueTriple(QWidget):
    def __init__(self, names, unit, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(3)
        self.values = []
        for i, name in enumerate(names):
            layout.addWidget(label(name, "secondary"), 0, i)
            value = label("—", "numeric")
            self.values.append(value)
            layout.addWidget(value, 1, i)
            layout.setColumnStretch(i, 1)
        self.setToolTip(unit)

    def set_values(self, values, decimals=3):
        for i, widget in enumerate(self.values):
            widget.setText(number(values[i] if values and len(values) > i else None, decimals))


class JointBar(QWidget):
    """Signed, finite display range; intentionally unrelated to robot limits."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = None
        self.tone = "blue"
        self.setMinimumHeight(9)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value):
        self.value = value if isinstance(value, (int, float)) and math.isfinite(value) else None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 2, self.width(), 5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#203649"))
        painter.drawRoundedRect(rect, 2, 2)
        center = self.width() / 2
        if self.value is not None:
            length = max(-180, min(180, self.value)) / 180 * (center - 2)
            painter.setBrush(QColor(COLORS[self.tone]))
            painter.drawRoundedRect(QRectF(min(center, center + length), 2, max(abs(length), 2), 5), 2, 2)
        painter.setPen(QPen(QColor("#70859b"), 1))
        painter.drawLine(QPointF(center, 0), QPointF(center, 9))


class ArmCard(Card):
    def __init__(self, side, parent=None):
        super().__init__(f"{side.upper()} ARM", parent=parent)
        self.side = side
        self.state_label = pill("OFFLINE")
        self.heading.addWidget(self.state_label)
        self.body.addWidget(label("TCP POSITION  /  m", "eyebrow"))
        self.position = ValueTriple(("X", "Y", "Z"), "Robot base TCP position, metres")
        self.body.addWidget(self.position)
        self.body.addWidget(label("ORIENTATION  /  degree", "eyebrow"))
        self.orientation = ValueTriple(("Roll", "Pitch", "Yaw"), "Quaternion converted to roll, pitch, yaw")
        self.body.addWidget(self.orientation)
        self.quaternion = label("q  — / — / — / —", "secondary")
        self.quaternion.setWordWrap(True)
        self.body.addWidget(self.quaternion)
        self.body.addSpacing(5)
        self.body.addWidget(label("JOINTS  /  degree", "eyebrow"))
        self.joint_rows = []
        joint_grid = QGridLayout()
        self.joint_grid = joint_grid
        joint_grid.setHorizontalSpacing(8)
        joint_grid.setVerticalSpacing(12)
        for i in range(6):
            name = label(f"J{i + 1}", "secondary")
            value = label("—", "numeric", Qt.AlignRight | Qt.AlignVCenter)
            value.setMinimumWidth(42)
            bar = JointBar()
            joint_grid.addWidget(name, i, 0)
            joint_grid.addWidget(value, i, 1)
            joint_grid.addWidget(bar, i, 2)
            self.joint_rows.append((value, bar))
        joint_grid.setColumnStretch(2, 1)
        self.body.addLayout(joint_grid)
        self.body.addWidget(label("显示范围 ±180° · 仅可视化", "secondary"))
        self.body.addSpacing(3)
        self.health_labels = {}
        health_grid = QGridLayout()
        self.health_grid = health_grid
        health_grid.setHorizontalSpacing(8)
        for i, name in enumerate(("Pose", "Input", "Robot", "Joint")):
            health_grid.addWidget(label(f"{name} age", "secondary"), i, 0)
            value = label("LOST", "numeric", Qt.AlignRight)
            self.health_labels[name] = value
            health_grid.addWidget(value, i, 1)
        self.body.addLayout(health_grid)
        self.deadman = label("GRIP  UNKNOWN", "eyebrow")
        self.cart = label("CART  UNKNOWN", "eyebrow")
        self.home = label("HOME  UNKNOWN", "eyebrow")
        self.body.addWidget(self.deadman)
        self.body.addWidget(self.cart)
        self.body.addWidget(self.home)
        self.reason = label("", "secondary")
        self.reason.setWordWrap(True)
        self.reason.setMinimumHeight(28)
        self.body.addWidget(self.reason)
        self.body.addStretch()

    def set_compact(self, compact):
        self.body.setSpacing(4 if compact else 8)
        self.joint_grid.setVerticalSpacing(6 if compact else 12)
        self.health_grid.setVerticalSpacing(2 if compact else 6)

    def update_arm(self, arm, controller):
        status = arm.adapter
        state = fresh_state(arm.status_health, status.state)
        set_state(self.state_label, state)
        self.state_label.setToolTip(f"Adapter reported: {status.state}\nStatus age: {age_text(arm.status_health)}")
        self.position.set_values(arm.robot_pose.position)
        self.orientation.set_values(arm.robot_pose.rpy_deg, 1)
        self.quaternion.setText("q  " + "  ".join(number(v, 3) for v in (arm.robot_pose.quaternion or (None,) * 4)))
        for (value_label, bar), value in zip(self.joint_rows, arm.joints_deg):
            value_label.setText(number(value, 1, "°"))
            bar.tone = tone_for(state)
            bar.set_value(value)
        self.setToolTip(arm.joints_error or arm.robot_pose.error)
        for name, health in (("Pose", controller.pose_health), ("Input", controller.inputs_health),
                             ("Robot", arm.robot_health), ("Joint", arm.joints_health)):
            widget = self.health_labels[name]
            set_state(widget, age_text(health), tone_for(health.state))
            widget.setToolTip(health.state + (": " + health.error if health.error else ""))
        live = arm.status_health.state == "ONLINE" and not status.parse_error
        set_state(self.deadman, "GRIP " + ("PRESSED" if status.deadman_pressed is True else "RELEASED" if status.deadman_pressed is False else "UNKNOWN") if live else "GRIP " + state,
                  "green" if live and status.deadman_pressed else "grey")
        for widget, prefix, ready in ((self.cart, "CART", status.command_path_ready),
                                       (self.home, "HOME", status.home_command_path_ready)):
            set_state(widget, prefix + " " + ("READY" if ready is True else "NOT READY" if ready is False else "UNKNOWN") if live else prefix + " " + state,
                      "green" if live and ready else "orange" if live and ready is False else "grey")
        reason = status.parse_error or status.reason or arm.joints_error or arm.robot_pose.error
        self.reason.setText(reason or "No active diagnostic")
        apply_tone(self.reason, "red" if status.parse_error or status.state == "FAULT" else "orange" if reason else "grey")


class OverviewCard(Card):
    def __init__(self, title, parent=None):
        super().__init__(title, parent=parent)
        self.body.setContentsMargins(12, 7, 12, 8)
        self.body.setSpacing(4)
        self.state_label = pill("OFFLINE")
        self.heading.addWidget(self.state_label)
        self.details = label("Awaiting topic data", "secondary")
        self.details.setWordWrap(True)
        self.body.addWidget(self.details)

    def update_value(self, state, details):
        set_state(self.state_label, state)
        self.details.setText(details)


class ControllerGlyph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(42, 54)
        self.tone = "blue"

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(COLORS[self.tone]), 1.4))
        p.setBrush(QColor("#172e44"))
        p.drawEllipse(QRectF(3, 2, 34, 27))
        path = QPainterPath()
        path.moveTo(12, 18)
        path.lineTo(26, 20)
        path.lineTo(30, 46)
        path.quadTo(22, 54, 16, 46)
        path.closeSubpath()
        p.drawPath(path)
        p.setBrush(QColor(COLORS[self.tone]))
        p.drawEllipse(QRectF(14, 11, 5, 5))
        p.drawEllipse(QRectF(24, 12, 3, 3))


class ControllerCard(Card):
    def __init__(self, side, parent=None):
        super().__init__(side.upper() + " CONTROLLER", parent=parent, role="inset")
        self.body.setContentsMargins(10, 7, 10, 8)
        self.body.setSpacing(4)
        self.side = side
        self.state_label = label("OFFLINE", "eyebrow")
        self.heading.addWidget(self.state_label)
        pose_row = QHBoxLayout()
        self.glyph = ControllerGlyph()
        pose_row.addWidget(self.glyph)
        pose_column = QVBoxLayout()
        pose_column.setSpacing(4)
        self.position = ValueTriple(("X", "Y", "Z"), "Quest world position / m")
        self.orientation = ValueTriple(("R", "P", "Y"), "Quest world orientation / degree")
        pose_column.addWidget(self.position)
        pose_column.addWidget(self.orientation)
        pose_row.addLayout(pose_column)
        self.body.addLayout(pose_row)
        self.timing = label("— Hz   ·   LOST", "secondary")
        self.body.addWidget(self.timing)
        self.input_timing = label("INPUTS  LOST", "secondary")
        self.body.addWidget(self.input_timing)
        self.analogs = []
        for name in ("Grip", "Index"):
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(label(name, "secondary"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            row.addWidget(bar, 1)
            value = label("—", "numeric", Qt.AlignRight)
            value.setMinimumWidth(30)
            row.addWidget(value)
            self.analogs.append((bar, value))
            self.body.addLayout(row)
        button_row = QHBoxLayout()
        button_row.addWidget(label("BUTTONS", "eyebrow"))
        button_row.addStretch()
        self.buttons = []
        for name in (("X", "Y") if side == "left" else ("A", "B")):
            widget = label(f"○ {name}", "numeric")
            button_row.addWidget(widget)
            self.buttons.append(widget)
        self.body.addLayout(button_row)

    def set_compact(self, compact):
        self.glyph.setVisible(not compact)
        self.heading.setSpacing(4 if compact else 7)
        self.body.setContentsMargins(6 if compact else 10, 7,
                                     6 if compact else 10, 8)

    def update_controller(self, controller):
        states = (controller.pose_health.state, controller.inputs_health.state)
        state = "INVALID" if "INVALID" in states else "ONLINE" if all(s == "ONLINE" for s in states) else "OFFLINE" if "OFFLINE" in states else "STALE"
        set_state(self.state_label, state)
        self.glyph.tone = tone_for(state)
        self.glyph.update()
        self.position.set_values(controller.pose.position)
        self.orientation.set_values(controller.pose.rpy_deg, 1)
        self.timing.setText(f"{number(controller.pose_health.hz, 1)} Hz  ·  {age_text(controller.pose_health)}")
        set_state(self.input_timing, f"INPUTS {controller.inputs_health.state} · {age_text(controller.inputs_health)}", tone_for(controller.inputs_health.state))
        for (bar, widget), value in zip(self.analogs, (controller.grip, controller.trigger)):
            valid = isinstance(value, (int, float)) and math.isfinite(value)
            bar.setValue(round(max(0, min(1, value)) * 100) if valid else 0)
            apply_tone(bar, "blue" if controller.inputs_health.state == "ONLINE" else "grey")
            widget.setText(number(value * 100 if valid else None, 0, "%"))
        for widget, name, pressed in zip(self.buttons, ("X", "Y") if self.side == "left" else ("A", "B"), (controller.button_lower, controller.button_upper)):
            live = controller.inputs_health.state == "ONLINE"
            widget.setText(f"{'●' if pressed and live else '○' if pressed is not None else '−'} {name}")
            apply_tone(widget, "green" if pressed and live else "grey")


class SafetyCard(Card):
    def __init__(self, parent=None):
        super().__init__("Safety & Command Paths", parent=parent, role="panel")
        self.body.setContentsMargins(12, 8, 12, 8)
        self.body.setSpacing(5)
        self.heading.addWidget(label("READ ONLY", "eyebrow"))
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.addWidget(label("OBSERVED STATUS", "eyebrow"), 0, 0)
        grid.addWidget(label("LEFT", "eyebrow"), 0, 1)
        grid.addWidget(label("RIGHT", "eyebrow"), 0, 2)
        self.fields = {}
        rows = (
            ("state", "State"), ("command_path_ready", "Cartesian path"),
            ("home_command_path_ready", "Home path"), ("counts", "Watchdog / Rearm"),
            ("max_cycle_period_ms", "Max cycle / ms"), ("home_action_state", "Home action"),
            ("preset", "Selection / Active"), ("gates", "Write / Output / Map"),
            ("fresh", "Q / I / R / J freshness"),
        )
        for i, (key, title) in enumerate(rows, 1):
            grid.addWidget(label(title, "secondary"), i, 0)
            widgets = []
            for column in (1, 2):
                value = label("—", "numeric")
                value.setWordWrap(True)
                value.setMinimumWidth(0)
                grid.addWidget(value, i, column)
                widgets.append(value)
            self.fields[key] = widgets
        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 3)
        self.body.addLayout(grid)
        hold = QHBoxLayout()
        hold.addWidget(label("Home hold", "secondary"))
        self.hold_bars = []
        for side in ("L", "R"):
            hold.addWidget(label(side, "eyebrow"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            apply_tone(bar, "orange")
            hold.addWidget(bar, 1)
            self.hold_bars.append(bar)
        self.body.addLayout(hold)
        self.reason = label("", "secondary")
        self.reason.setWordWrap(True)
        self.body.addWidget(self.reason)

    def update_arms(self, left, right):
        diagnostics = []
        for index, arm in enumerate((left, right)):
            status = arm.adapter
            live = arm.status_health.state == "ONLINE" and not status.parse_error
            state = fresh_state(arm.status_health, status.state)
            def boolean(value):
                return "Y" if value is True else "N" if value is False else "?"
            values = {
                "state": state,
                "command_path_ready": "READY" if live and status.command_path_ready is True else "BLOCKED" if live and status.command_path_ready is False else state if not live else "UNKNOWN",
                "home_command_path_ready": "READY" if live and status.home_command_path_ready is True else "BLOCKED" if live and status.home_command_path_ready is False else state if not live else "UNKNOWN",
                "counts": f"{number(status.watchdog_count, 0)} / {number(status.rearm_count, 0)}",
                "max_cycle_period_ms": number(status.max_cycle_period_ms, 2),
                "home_action_state": status.home_action_state if live else state,
                "preset": f"{status.joint_preset_selection or '—'} / {status.joint_preset_active or '—'}",
                "gates": " / ".join(boolean(v) for v in (status.hardware_write_enabled, status.hardware_output_available, status.mapping_verified)),
                "fresh": " / ".join(boolean(v) for v in (status.quest_pose_fresh, status.inputs_fresh, status.robot_fresh, status.joint_state_fresh)),
            }
            for key, value in values.items():
                widget = self.fields[key][index]
                set_state(widget, value, tone_for(value) if key in ("state", "home_action_state") else "green" if value == "READY" else "orange" if value == "BLOCKED" else "grey" if not live else "blue")
            progress = status.home_hold_progress
            valid = live and isinstance(progress, (int, float)) and math.isfinite(progress)
            self.hold_bars[index].setValue(round(max(0, min(1, progress)) * 100) if valid else 0)
            self.hold_bars[index].setToolTip(number(progress * 100 if valid else None, 0, "%"))
            reason = status.parse_error or status.reason
            if reason:
                diagnostics.append(f"{arm.side.upper()}: {reason}")
        self.reason.setText("  ·  ".join(diagnostics) or "Adapter owns safety decisions · monitored only")
        apply_tone(self.reason, "orange" if diagnostics else "grey")


class LinkerHandCard(Card):
    CHANNELS = ("Thumb Pitch", "Thumb Yaw", "Index", "Middle", "Ring", "Little", "Thumb Roll")

    def __init__(self, parent=None):
        super().__init__("Right LinkerHand L7", parent=parent, role="panel")
        self.body.setContentsMargins(12, 8, 12, 8)
        self.body.setSpacing(4)
        self.state_label = pill("OFFLINE")
        self.heading.addWidget(self.state_label)
        self.summary = label("COMM —   ·   INPUT —   ·   TRIGGER —", "secondary")
        self.summary.setWordWrap(True)
        self.body.addWidget(self.summary)
        self.toggle = label("OPEN / CLOSED: UNKNOWN", "eyebrow")
        self.body.addWidget(self.toggle)
        grid = QGridLayout()
        grid.setSpacing(2)
        grid.addWidget(label("HAND CHANNEL · 0–255", "eyebrow"), 0, 0)
        grid.addWidget(label("TARGET", "eyebrow"), 0, 1)
        grid.addWidget(label("ACTUAL", "eyebrow"), 0, 2)
        self.channels = []
        for i, name in enumerate(self.CHANNELS, 1):
            grid.addWidget(label(name, "secondary"), i, 0)
            target = label("—", "numeric", Qt.AlignRight)
            actual = label("—", "numeric", Qt.AlignRight)
            bar = QProgressBar()
            bar.setRange(0, 255)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            grid.addWidget(target, i, 1)
            grid.addWidget(actual, i, 2)
            grid.addWidget(bar, i, 3)
            self.channels.append((target, actual, bar))
        grid.setColumnStretch(3, 1)
        self.body.addLayout(grid)
        self.faults = label("Fault codes: —", "secondary")
        self.faults.setWordWrap(True)
        self.body.addWidget(self.faults)
        self.body.addWidget(label("Left End Effector  ·  未配置 / Not Configured", "secondary"))

    def update_hand(self, hand):
        state = fresh_state(hand.health, hand.state)
        set_state(self.state_label, state)
        live = hand.health.state == "ONLINE" and not hand.parse_error
        comm = "OK" if hand.communication_ok is True else "NO" if hand.communication_ok is False else "—"
        input_state = "FRESH" if hand.input_fresh is True else "STALE" if hand.input_fresh is False else "—"
        self.summary.setText(f"COMM {comm}  ·  INPUT {input_state}  ·  {age_text(hand.health)}")
        self.toggle.setText(f"{hand.hand_toggle_state or 'UNKNOWN'}  ·  Trigger {number(hand.trigger_value, 2)}  ·  Armed {'Y' if hand.trigger_armed is True else 'N' if hand.trigger_armed is False else '?'}")
        apply_tone(self.toggle, "blue" if live else "grey")
        for i, (target, actual, bar) in enumerate(self.channels):
            target_value = hand.target[i] if hand.target and len(hand.target) > i else None
            actual_value = hand.actual[i] if hand.actual and len(hand.actual) > i else None
            target.setText(number(target_value, 0))
            actual.setText(number(actual_value, 0))
            value = actual_value if actual_value is not None else target_value
            valid = isinstance(value, (int, float)) and math.isfinite(value)
            bar.setValue(round(max(0, min(255, value))) if valid else 0)
            apply_tone(bar, "green" if live and actual_value is not None else "blue" if live else "grey")
            bar.setToolTip("Actual feedback" if actual_value is not None else "Target only; no actual feedback")
        faults = ", ".join(str(v) for v in hand.fault_codes) if hand.fault_codes is not None else "unavailable"
        diagnostic = hand.parse_error or hand.error
        self.faults.setText("Fault codes: " + faults + (" · " + diagnostic if diagnostic else ""))
        apply_tone(self.faults, "red" if diagnostic or hand.fault_codes and any(hand.fault_codes) else "grey")


class RobotOverviewWidget(QWidget):
    """Six-link abstract drawing; an illustration, never inferred kinematics."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.left_state = "OFFLINE"
        self.right_state = "OFFLINE"
        self.setMinimumWidth(150)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def update_states(self, left, right):
        self.left_state, self.right_state = left, right
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        scale = min(w / 320, h / 470)
        p.translate(w / 2, h / 2)
        p.scale(scale, scale)
        p.translate(-160, -228)
        p.setPen(QPen(QColor("#20364b"), 0.8))
        for x in range(-100, 430, 35):
            p.drawLine(QPointF(160, 270), QPointF(x, 448))
        for y in (298, 326, 359, 399, 448):
            p.drawLine(QPointF(15, y), QPointF(305, y))
        # Pedestal and shoulder bridge, shaded with flat engineering colors.
        p.setPen(QPen(QColor("#7089a1"), 1.3))
        p.setBrush(QColor("#283d52"))
        p.drawPolygon(QPolygonF([QPointF(124, 376), QPointF(196, 376), QPointF(214, 399), QPointF(107, 399)]))
        p.setBrush(QColor("#415a70"))
        p.drawRoundedRect(QRectF(140, 235, 40, 145), 6, 6)
        p.setBrush(QColor("#6c8395"))
        p.drawRoundedRect(QRectF(98, 221, 124, 30), 11, 11)
        p.setBrush(QColor("#233a51"))
        p.drawRoundedRect(QRectF(151, 246, 18, 107), 3, 3)
        points = [(107, 235), (74, 204), (62, 147), (88, 107), (107, 84), (94, 65), (82, 49)]
        for side, state in (("left", self.left_state), ("right", self.right_state)):
            arm_points = [QPointF(x if side == "left" else 320 - x, y) for x, y in points]
            color = QColor(COLORS[tone_for(state)])
            for i in range(6):
                p.setPen(QPen(QColor("#1b2b3b"), 25 if i < 3 else 15, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(arm_points[i], arm_points[i + 1])
                p.setPen(QPen(QColor("#758a9b"), 19 if i < 3 else 11, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(arm_points[i], arm_points[i + 1])
                p.setPen(QPen(QColor("#c0ccd5"), 2, Qt.SolidLine, Qt.RoundCap))
                offset = QPointF(-3, -2)
                p.drawLine(arm_points[i] + offset, arm_points[i + 1] + offset)
            for i, point in enumerate(arm_points[:-1]):
                radius = 10 if i < 3 else 6
                p.setPen(QPen(color, 2))
                p.setBrush(QColor("#1b344a"))
                p.drawEllipse(point, radius, radius)
                p.setBrush(color)
                p.setPen(Qt.NoPen)
                p.drawEllipse(point, 2.5, 2.5)
            end = arm_points[-1]
            p.setPen(QPen(QColor("#a2b3c2"), 3, Qt.SolidLine, Qt.RoundCap))
            direction = -1 if side == "left" else 1
            for spread in (-5, 5):
                p.drawLine(end + QPointF(spread, -1), end + QPointF(spread + direction * 5, -18))
            p.setPen(color)
            p.setFont(QFont("DejaVu Sans", 10, QFont.DemiBold))
            p.drawText(QRectF(0 if side == "left" else 238, 14, 82, 18), Qt.AlignCenter, side.upper())
            p.setFont(QFont("DejaVu Sans", 8))
            p.drawText(QRectF(0 if side == "left" else 224, 278, 96, 18), Qt.AlignCenter, state)
        origin = QPointF(160, 427)
        for destination, text, color in ((QPointF(117, 450), "X", "#e88b91"),
                                        (QPointF(205, 445), "Y", "#36d5a4"),
                                        (QPointF(160, 383), "Z", "#4ea6ee")):
            p.setPen(QPen(QColor(color), 1.7))
            p.drawLine(origin, destination)
            p.drawText(destination + QPointF(5, 4), text)
        p.setPen(QColor(SECONDARY))
        p.setFont(QFont("DejaVu Sans", 8))
        p.drawText(QRectF(30, 466, 260, 22), Qt.AlignCenter, "6DoF schematic · not kinematics")
