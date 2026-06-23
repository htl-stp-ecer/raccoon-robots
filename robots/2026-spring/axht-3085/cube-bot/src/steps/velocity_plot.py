"""Educational velocity-plotting steps for the test mission.

These steps run a real drive or turn move and, while doing so, record the
**commanded** velocity (the setpoint the motion profile asks for each control
cycle) and the **measured** velocity (what the encoders actually report). After
the move they render a matplotlib plot of commanded vs. measured velocity.

The purpose is teaching: the gap between the two curves is exactly what the PID
controller is fighting to close, so the plot makes "how a PID works" visible.

Notes on what the framework exposes
-----------------------------------
* A linear drive (:class:`raccoon.motion.LinearMotion`) records full per-cycle
  telemetry, so :class:`PlotDriveVelocity` shows a *true* commanded-vs-measured
  velocity curve.
* A turn (:class:`raccoon.motion.TurnMotion`) only exposes the measured
  (filtered) angular velocity, not the internal setpoint. So
  :class:`PlotTurnVelocity` plots the measured angular velocity against the
  commanded *cruise* speed of the trapezoidal profile (the speed the controller
  saturates at). This still shows the accelerate / cruise / decelerate shape.

Runtime
-------
This runs on the robot (the Pi) because it commands the motors. The Pi has no
interactive display, so plots are saved as PNG files with the headless "Agg"
backend, into a ``velocity_plots/`` directory at the project root. A CSV of the
raw samples is written alongside each plot so the data survives even if
matplotlib is unavailable.
"""

from __future__ import annotations

import asyncio
import csv
import math
from pathlib import Path

from raccoon import *  # noqa: F403  (Step, dsl_step, ... - project convention)
from raccoon.motion import (
    LinearAxis,
    LinearMotion,
    LinearMotionConfig,
    TurnConfig,
    TurnMotion,
)

# Save plots into the project root (this file is at <root>/src/steps/), not /tmp,
# so the output lives with the project and survives reboots.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUT_DIR = str(_PROJECT_ROOT / "velocity_plots")
_HZ = 100  # control-loop frequency, matches the framework's MotionStep default


def _next_free_path(directory: str, stem: str, ext: str) -> Path:
    """Return ``directory/stem.ext``, adding ``_2``, ``_3`` ... if it exists.

    Keeps a history of runs instead of overwriting the previous plot.
    """
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate = out_dir / f"{stem}.{ext}"
    n = 2
    while candidate.exists():
        candidate = out_dir / f"{stem}_{n}.{ext}"
        n += 1
    return candidate


@dsl_step(tags=["motion", "education", "plot"])  # noqa: F405
class PlotDriveVelocity(Step):  # noqa: F405
    """Drive forward (or strafe) and plot commanded vs. measured velocity.

    A drop-in, instrumented replacement for ``drive_forward`` intended for
    teaching how the velocity PID tracks the motion profile.

    Args:
        distance_cm: Distance to drive, in centimeters. Negative drives in
            reverse.
        speed: Speed scale of the motion profile (0.0--1.0).
        axis: ``"forward"`` (default) or ``"lateral"`` (strafe).
        out_dir: Directory for the PNG/CSV output. Default
            ``<project_root>/velocity_plots``.
        timeout: Max seconds before the move is aborted. Default 15.0.
    """

    def __init__(
        self,
        distance_cm: float = 50,
        speed: float = 1.0,
        axis: str = "forward",
        out_dir: str = _DEFAULT_OUT_DIR,
        timeout: float = 15.0,
    ):
        super().__init__()
        self.distance_cm = distance_cm
        self.speed = speed
        self.axis = (
            LinearAxis.Lateral
            if isinstance(axis, str) and axis.lower().startswith("l")
            else LinearAxis.Forward
        )
        self.out_dir = out_dir
        self.timeout = timeout

    def _generate_signature(self) -> str:
        return f"PlotDriveVelocity({self.distance_cm}cm, speed={self.speed:.2f})"

    async def _execute_step(self, robot) -> None:
        from raccoon.step.motion._heading_utils import get_world_heading_rad

        distance_m = self.distance_cm / 100.0

        config = LinearMotionConfig()
        config.axis = self.axis
        config.distance_m = distance_m
        config.speed_scale = self.speed
        config.target_heading_rad = get_world_heading_rad(robot)
        config.has_distance_target = True

        motion = LinearMotion(
            robot.drive, robot.odometry, robot.motion_pid_config, config
        )
        motion.start()

        rate = 1 / _HZ
        loop = asyncio.get_event_loop()
        t0 = loop.time()
        last = t0 - rate

        while not motion.is_finished():
            now = loop.time()
            if now - t0 > self.timeout:
                self.warn(f"PlotDriveVelocity timed out after {self.timeout:.1f}s")
                break
            dt = max(now - last, 0.0)
            last = now
            if dt < 1e-4:
                await asyncio.sleep(rate)
                continue
            motion.update(dt)
            await asyncio.sleep(rate)

        robot.drive.hard_stop()

        telemetry = list(motion.get_telemetry())
        if not telemetry:
            self.warn("No telemetry collected - nothing to plot.")
            return

        axis_name = "fwd" if self.axis == LinearAxis.Forward else "lat"
        stem = f"drive_{axis_name}_{abs(self.distance_cm):.0f}cm_speed{self.speed:.2f}"
        self._write_csv(stem, telemetry)
        self._plot(robot, stem, telemetry)

    def _write_csv(self, stem: str, telemetry: list) -> None:
        path = _next_free_path(self.out_dir, stem, "csv")
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time_s", "commanded_velocity_mps", "measured_velocity_mps"])
            for t in telemetry:
                w.writerow(
                    [
                        f"{t.time_s:.4f}",
                        f"{t.setpoint_velocity_mps:.4f}",
                        f"{t.filtered_velocity_mps:.4f}",
                    ]
                )
        self.info(f"Wrote velocity data: {path}")

    def _plot(self, robot, stem: str, telemetry: list) -> None:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as exc:  # noqa: BLE001
            self.warn(f"matplotlib unavailable, skipping plot ({exc}). CSV was saved.")
            return

        times = [t.time_s for t in telemetry]
        commanded = [t.setpoint_velocity_mps for t in telemetry]
        measured = [t.filtered_velocity_mps for t in telemetry]
        error = [c - m for c, m in zip(commanded, measured)]

        # Pull the live PID gains so the plot documents what was actually tuned.
        vx_pid = robot.drive.get_velocity_control_config().vx.pid
        dist = robot.motion_pid_config.distance
        gain_text = (
            "Velocity PID (vx)\n"
            f"  kp={vx_pid.kp:g}  ki={vx_pid.ki:g}  kd={vx_pid.kd:g}\n"
            "Distance PID\n"
            f"  kp={dist.kp:g}  ki={dist.ki:g}  kd={dist.kd:g}"
        )

        fig, (ax_v, ax_e) = plt.subplots(
            2, 1, figsize=(10, 7), sharex=True, height_ratios=[3, 1]
        )

        ax_v.plot(times, commanded, "--", color="#1f77b4", lw=2,
                  label="Commanded (setpoint)")
        ax_v.plot(times, measured, "-", color="#d62728", lw=1.8,
                  label="Measured (encoders)")
        ax_v.fill_between(times, commanded, measured, color="#d62728", alpha=0.12,
                          label="Tracking error")
        ax_v.set_ylabel("Velocity (m/s)")
        ax_v.set_title(
            f"PID velocity tracking — drive {self.distance_cm:.0f} cm "
            f"@ speed {self.speed:.2f}"
        )
        ax_v.grid(True, alpha=0.3)
        ax_v.legend(loc="upper right")
        ax_v.text(
            0.015, 0.97, gain_text, transform=ax_v.transAxes, va="top", ha="left",
            fontsize=9, family="monospace",
            bbox={"boxstyle": "round", "facecolor": "#fffbe6", "alpha": 0.9},
        )

        ax_e.axhline(0, color="#888888", lw=1)
        ax_e.plot(times, error, "-", color="#2ca02c", lw=1.2)
        ax_e.fill_between(times, error, 0, color="#2ca02c", alpha=0.15)
        ax_e.set_ylabel("Error (m/s)")
        ax_e.set_xlabel("Time (s)")
        ax_e.grid(True, alpha=0.3)

        fig.tight_layout()
        path = _next_free_path(self.out_dir, stem, "png")
        fig.savefig(path, dpi=130)
        plt.close(fig)
        self.info(f"Saved velocity plot: {path}")


@dsl_step(tags=["motion", "education", "plot"])  # noqa: F405
class PlotTurnVelocity(Step):  # noqa: F405
    """Turn in place and plot the measured angular velocity.

    A drop-in, instrumented replacement for ``turn_right`` / ``turn_left``.

    The turn controller does not expose its internal angular-velocity setpoint,
    so the plot shows the measured angular velocity against the commanded
    *cruise* speed of the trapezoidal profile (the rate the controller saturates
    at). The accelerate / cruise / decelerate shape and the settling behaviour
    are still clearly visible.

    Args:
        degrees: Angle to rotate, in degrees (> 0).
        direction: ``"right"`` (clockwise, default) or ``"left"``.
        speed: Speed scale of the profile (0.0--1.0).
        out_dir: Directory for the PNG/CSV output.
        timeout: Max seconds before the move is aborted. Default 15.0.
    """

    def __init__(
        self,
        degrees: float = 90,
        direction: str = "right",
        speed: float = 1.0,
        out_dir: str = _DEFAULT_OUT_DIR,
        timeout: float = 15.0,
    ):
        super().__init__()
        self.degrees = degrees
        self.direction = direction
        self.speed = speed
        # +1 = CCW (left), -1 = CW (right), matching raccoon's turn convention.
        self._sign = 1.0 if str(direction).lower().startswith("l") else -1.0
        self.out_dir = out_dir
        self.timeout = timeout

    def _generate_signature(self) -> str:
        return f"PlotTurnVelocity({self.degrees}deg, {self.direction}, speed={self.speed:.2f})"

    async def _execute_step(self, robot) -> None:
        config = TurnConfig()
        config.target_angle_rad = self._sign * math.radians(self.degrees)
        config.speed_scale = self.speed
        config.has_angle_target = True

        motion = TurnMotion(
            robot.drive, robot.odometry, robot.motion_pid_config, config
        )
        motion.start()

        # The commanded cruise rate of the trapezoidal profile.
        cruise = self._sign * self.speed * robot.motion_pid_config.angular.max_velocity

        samples: list[tuple[float, float]] = []  # (time_s, measured_wz)
        rate = 1 / _HZ
        loop = asyncio.get_event_loop()
        t0 = loop.time()
        last = t0 - rate

        while not motion.is_finished():
            now = loop.time()
            if now - t0 > self.timeout:
                self.warn(f"PlotTurnVelocity timed out after {self.timeout:.1f}s")
                break
            dt = max(now - last, 0.0)
            last = now
            if dt < 1e-4:
                await asyncio.sleep(rate)
                continue
            motion.update(dt)
            samples.append((now - t0, motion.get_filtered_velocity()))
            await asyncio.sleep(rate)

        robot.drive.hard_stop()

        if not samples:
            self.warn("No samples collected - nothing to plot.")
            return

        stem = f"turn_{self.direction}_{self.degrees:.0f}deg_speed{self.speed:.2f}"
        self._write_csv(stem, samples, cruise)
        self._plot(robot, stem, samples, cruise)

    def _write_csv(self, stem: str, samples: list, cruise: float) -> None:
        path = _next_free_path(self.out_dir, stem, "csv")
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["time_s", "commanded_cruise_radps", "measured_velocity_radps"]
            )
            for t, wz in samples:
                w.writerow([f"{t:.4f}", f"{cruise:.4f}", f"{wz:.4f}"])
        self.info(f"Wrote angular-velocity data: {path}")

    def _plot(self, robot, stem: str, samples: list, cruise: float) -> None:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as exc:  # noqa: BLE001
            self.warn(f"matplotlib unavailable, skipping plot ({exc}). CSV was saved.")
            return

        times = [t for t, _ in samples]
        measured = [wz for _, wz in samples]

        head = robot.motion_pid_config.heading
        max_w = robot.motion_pid_config.angular.max_velocity
        gain_text = (
            "Heading PID\n"
            f"  kp={head.kp:g}  ki={head.ki:g}  kd={head.kd:g}\n"
            f"max angular vel = {max_w:g} rad/s"
        )

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axhline(
            cruise, ls="--", color="#1f77b4", lw=2,
            label="Commanded cruise (profile max)",
        )
        ax.plot(times, measured, "-", color="#d62728", lw=1.8,
                label="Measured (gyro/encoders)")
        ax.set_ylabel("Angular velocity (rad/s)")
        ax.set_xlabel("Time (s)")
        ax.set_title(
            f"PID turn tracking — {self.direction} {self.degrees:.0f}° "
            f"@ speed {self.speed:.2f}"
        )
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
        ax.text(
            0.015, 0.97, gain_text, transform=ax.transAxes, va="top", ha="left",
            fontsize=9, family="monospace",
            bbox={"boxstyle": "round", "facecolor": "#fffbe6", "alpha": 0.9},
        )

        fig.tight_layout()
        path = _next_free_path(self.out_dir, stem, "png")
        fig.savefig(path, dpi=130)
        plt.close(fig)
        self.info(f"Saved turn plot: {path}")


__all__ = ["PlotDriveVelocity", "PlotTurnVelocity"]
