"""Peak-tracking turn: full sweep then turn to absolute peak heading."""
from __future__ import annotations

import csv
import math
import os
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

#import matplotlib
#matplotlib.use("Agg")
#import matplotlib.pyplot as plt

from raccoon import dsl
from raccoon.motion import TurnConfig, TurnMotion
from raccoon.step.motion.motion_step import MotionStep

from src.service.range_finder_service import RangeFinderService

if TYPE_CHECKING:
    from raccoon.robot.api import GenericRobot

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs", "turn_to_peak")


class _Phase(Enum):
    SWEEP = 1   # full sweep, tracking peak heading
    RETURN = 2  # turning to absolute peak heading


@dsl(hidden=True)
class TurnToPeakStep(MotionStep):
    """Full sweep tracking peak sensor value, then turn to that absolute heading."""

    STUCK_WINDOW = 0.3          # seconds of no heading change to consider stuck
    STUCK_THRESHOLD_DEG = 2.0   # minimum heading change within window

    PIPE_RADIUS_CM = 1.05       # 2.1 cm diameter pipe
    FIT_WINDOW_MULT = 2.0       # fit within ±(mult × half-angle) of peak
    RIVAL_PEAK_RATIO = 0.95     # two peaks within this ratio trigger sweep-center tiebreak

    def __init__(self, direction: float, turn_speed: float, sweep_deg: float):
        super().__init__()
        self._direction = direction
        self._turn_speed = turn_speed
        self._sweep_deg = sweep_deg
        self._phase = _Phase.SWEEP
        self._motion: TurnMotion | None = None
        self._peak_value: float = 0.0
        self._peak_heading: float = 0.0
        self._service: RangeFinderService | None = None
        self._stuck_ref_heading: float = 0.0
        self._stuck_ref_time: float = 0.0
        self._elapsed: float = 0.0
        self._sweep_samples: list[tuple[float, float]] = []  # (heading_rad, filtered_value)
        self._log_rows: list[list] = []
        self._decision_meta: dict = {}  # filled by _find_peak_heading

    def _generate_signature(self) -> str:
        d = "right" if self._direction < 0 else "left"
        return f"TurnToPeak(dir={d}, speed={self._turn_speed:.2f}, sweep={self._sweep_deg:.0f})"

    def _make_turn(self, robot: GenericRobot, angle_rad: float) -> TurnMotion:
        cfg = TurnConfig()
        cfg.target_angle_rad = angle_rad
        cfg.speed_scale = self._turn_speed
        motion = TurnMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        motion.start()
        return motion

    def on_start(self, robot: GenericRobot) -> None:
        self._service = robot.get_service(RangeFinderService)
        rf = self._service.range_finder
        rf.reset_filter()

        # Start full sweep in the given direction
        sweep_rad = self._direction * math.radians(self._sweep_deg)
        self._motion = self._make_turn(robot, sweep_rad)
        self._phase = _Phase.SWEEP

        # Initialize peak and stuck detection
        self._peak_value = rf.read_filtered()
        self._peak_heading = robot.odometry.get_heading()
        self._stuck_ref_heading = self._peak_heading
        self._stuck_ref_time = 0.0
        self._elapsed = 0.0

        # Reset per-run state (step instance may be reused across runs)
        self._sweep_samples = []
        self._log_rows = []
        self._decision_meta = {}

        self.info(f"Peak turn: sweeping {self._sweep_deg:.0f} deg")

    def _is_stuck(self, heading: float, dt: float) -> bool:
        self._elapsed += dt
        heading_delta = abs(math.degrees(heading - self._stuck_ref_heading))
        if heading_delta > self.STUCK_THRESHOLD_DEG:
            self._stuck_ref_heading = heading
            self._stuck_ref_time = self._elapsed
        return self._elapsed - self._stuck_ref_time >= self.STUCK_WINDOW

    def _find_peak_heading(self) -> tuple[float, float]:
        """Find the true peak center using pipe geometry.

        The target is a 2.1 cm diameter cylinder.  At the measured distance
        the pipe subtends a known angular width, giving us a tight fit
        window around the highest reading.  A parabola fitted inside that
        window exploits the cylinder's symmetry to pin-point the center.

        If a rival peak of similar height (within ``RIVAL_PEAK_RATIO``)
        exists outside the window, prefer whichever peak is **narrower**
        (larger ``|a|`` curvature).  A 2.1 cm pipe always produces a
        sharper peak than a human leg, so this reliably picks the pipe.
        """
        if not self._sweep_samples:
            return self._peak_heading, self._peak_value

        headings_rad = [h for h, _ in self._sweep_samples]
        values = [v for _, v in self._sweep_samples]
        peak_val = max(values)
        peak_idx = values.index(peak_val)
        peak_h = headings_rad[peak_idx]

        # Estimate distance from peak ADC reading, derive fit window
        fit_half = self._geometry_fit_half_angle(peak_val)

        # Primary: fit parabola in the geometry window around global max
        primary_center, primary_curvature = self._fit_window(
            headings_rad, values, peak_h, fit_half,
        )

        # Check for a rival peak outside the primary window
        rival_center, rival_val, rival_curvature = self._find_rival_peak(
            headings_rad, values, primary_center, fit_half,
        )

        # Tiebreak: if rival is close in height, prefer the NARROWER peak
        # (larger |curvature|) — a 2.1cm pipe is always sharper than a person.
        # Both peaks must have negative curvature (concave down = valid peak);
        # positive curvature means the fit window only saw one side (edge artifact).
        used_rival = (rival_val is not None
                      and rival_val / peak_val >= self.RIVAL_PEAK_RATIO
                      and rival_curvature < 0
                      and (primary_curvature >= 0
                           or abs(rival_curvature) > abs(primary_curvature)))

        if used_rival:
            best_h = rival_center
        else:
            best_h = primary_center

        best_v = min(self._sweep_samples,
                     key=lambda hv: abs(hv[0] - best_h))[1]

        volts = peak_val * 5.0 / 4095.0
        est_dist = 27.0 / max(volts, 0.1)
        self._decision_meta = {
            "est_distance_cm": round(min(80, max(5, est_dist)), 1),
            "fit_half_deg": round(math.degrees(fit_half), 1),
            "raw_peak_heading_deg": round(math.degrees(peak_h), 1),
            "raw_peak_value": round(peak_val, 0),
            "primary_center_deg": round(math.degrees(primary_center), 1),
            "primary_curvature": round(primary_curvature, 4),
            "rival_value": round(rival_val, 0) if rival_val is not None else None,
            "rival_center_deg": round(math.degrees(rival_center), 1) if rival_val is not None else None,
            "rival_ratio": round(rival_val / peak_val, 3) if rival_val is not None else None,
            "rival_curvature": round(rival_curvature, 4) if rival_val is not None else None,
            "used_rival": used_rival,
            "chosen_heading_deg": round(math.degrees(best_h), 1),
            "num_sweep_samples": len(self._sweep_samples),
        }

        return best_h, best_v

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _geometry_fit_half_angle(self, peak_adc: float) -> float:
        """Return the fit half-window (rad) based on pipe geometry."""
        volts = peak_adc * 5.0 / 4095.0
        distance_cm = 27.0 / max(volts, 0.1)
        distance_cm = max(5.0, min(80.0, distance_cm))
        half_angle = math.asin(
            min(1.0, self.PIPE_RADIUS_CM / distance_cm)
        )
        return half_angle * self.FIT_WINDOW_MULT

    def _fit_window(
        self,
        headings: list[float],
        values: list[float],
        centre: float,
        half: float,
    ) -> tuple[float, float]:
        """Fit a parabola to samples within *centre ± half*.

        Returns ``(vertex_heading, curvature_a)``.  A more negative *a*
        means a narrower, sharper peak (more pipe-like).
        Falls back to ``(centre, 0.0)`` on bad fits.
        """
        wh = [h for h, v in zip(headings, values)
              if centre - half <= h <= centre + half]
        wv = [v for h, v in zip(headings, values)
              if centre - half <= h <= centre + half]
        if len(wh) < 3:
            return centre, 0.0
        return self._parabola_vertex(wh, wv, fallback=centre)

    def _find_rival_peak(
        self,
        headings: list[float],
        values: list[float],
        primary_center: float,
        half: float,
    ) -> tuple[float, float | None, float]:
        """Find the highest reading outside the primary fit window.

        Returns ``(center, value, curvature)``."""
        outside = [
            (h, v) for h, v in zip(headings, values)
            if not (primary_center - half <= h <= primary_center + half)
        ]
        if not outside:
            return 0.0, None, 0.0
        rival_h, rival_v = max(outside, key=lambda hv: hv[1])
        rival_center, rival_curvature = self._fit_window(
            headings, values, rival_h, half,
        )
        return rival_center, rival_v, rival_curvature

    @staticmethod
    def _parabola_vertex(
        headings: list[float],
        values: list[float],
        fallback: float,
    ) -> tuple[float, float]:
        """Least-squares parabola fit.

        Returns ``(vertex_heading, a)`` where *a* is the quadratic
        coefficient (negative = concave-down peak, larger ``|a|`` =
        narrower peak).  Falls back to ``(fallback, 0.0)``."""
        n = len(headings)
        s0 = float(n)
        s1 = sum(headings)
        s2 = sum(h * h for h in headings)
        s3 = sum(h * h * h for h in headings)
        s4 = sum(h * h * h * h for h in headings)
        sy = sum(values)
        shy = sum(h * v for h, v in zip(headings, values))
        sh2y = sum(h * h * v for h, v in zip(headings, values))

        det = (s0 * (s2 * s4 - s3 * s3)
               - s1 * (s1 * s4 - s3 * s2)
               + s2 * (s1 * s3 - s2 * s2))
        if abs(det) < 1e-12:
            return fallback, 0.0

        a = ((sy * (s2 * s4 - s3 * s3)
              - s1 * (shy * s4 - sh2y * s3)
              + s2 * (shy * s3 - sh2y * s2)) / det)
        b = ((s0 * (shy * s4 - sh2y * s3)
              - sy * (s1 * s4 - s3 * s2)
              + s2 * (s1 * sh2y - s3 * shy)) / det)

        if a >= 0:
            return fallback, a

        vertex = -b / (2.0 * a)

        lo, hi = min(headings), max(headings)
        margin = (hi - lo) * 0.25
        if vertex < lo - margin or vertex > hi + margin:
            return fallback, a

        return vertex, a

    def _transition_to_return(self, robot: GenericRobot, reason: str) -> None:
        self._peak_heading, self._peak_value = self._find_peak_heading()
        self.info(
            f"Peak turn: {reason}, peak={self._peak_value:.0f} "
            f"at {math.degrees(self._peak_heading):.1f} deg"
        )
        error_rad = robot.odometry.get_heading_error(self._peak_heading)
        self._motion = self._make_turn(robot, error_rad)
        self._phase = _Phase.RETURN

    def _save_log(self) -> None:
        if not self._log_rows:
            return
        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(LOG_DIR, f"{stamp}.csv")

        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)

            # --- metadata header (comment lines) ---
            meta = self._decision_meta
            w.writerow(["# algorithm=geometry_parabola_fit"])
            w.writerow([f"# pipe_diameter_cm={self.PIPE_RADIUS_CM * 2}"])
            w.writerow([f"# fit_window_mult={self.FIT_WINDOW_MULT}"])
            w.writerow([f"# rival_peak_ratio={self.RIVAL_PEAK_RATIO}"])
            for key, val in meta.items():
                w.writerow([f"# {key}={val}"])

            # --- sample data ---
            w.writerow([
                "elapsed_s", "heading_deg",
                "raw_value", "filtered_value",
                "running_peak_value", "running_peak_heading_deg",
                "phase",
            ])
            w.writerows(self._log_rows)

        self.info(f"Peak turn log saved: {csv_path}")

    def on_update(self, robot: GenericRobot, dt: float) -> bool:
        self._motion.update(dt)
        rf = self._service.range_finder
        value = rf.read_filtered()
        raw_value = rf.last_raw
        heading = robot.odometry.get_heading()

        self._log_rows.append([
            self._elapsed,
            math.degrees(heading),
            raw_value,
            value,
            self._peak_value,
            math.degrees(self._peak_heading),
            self._phase.name,
        ])

        if self._phase == _Phase.SWEEP:
            self._sweep_samples.append((heading, value))
            if value > self._peak_value:
                self._peak_value = value
                self._peak_heading = heading

            if self._is_stuck(heading, dt):
                self._transition_to_return(robot, "stuck — aborting sweep")
            elif self._motion.is_finished():
                self._transition_to_return(robot, "sweep done")
            else:
                return False
            return False

        # RETURN phase
        done = self._motion.is_finished()
        if done:
            self._save_log()
        return done


@dsl(tags=["motion", "sensor"])
def turn_to_peak(
    direction: float = -1.0,
    turn_speed: float = 0.5,
    sweep_deg: float = 35,
) -> TurnToPeakStep:
    """Peak-tracking turn using the ET range finder.

    Does a full sweep, tracking the heading of the maximum sensor reading,
    then turns to that absolute heading.

    Args:
        direction: -1.0 for right, +1.0 for left (default: right).
        turn_speed: Fraction of max angular speed, 0.0-1.0 (default 0.5).
        sweep_deg: Degrees to sweep (default 30).

    Returns:
        A TurnToPeakStep instance.
    """
    return TurnToPeakStep(
        direction=direction,
        turn_speed=turn_speed,
        sweep_deg=sweep_deg,
    )
