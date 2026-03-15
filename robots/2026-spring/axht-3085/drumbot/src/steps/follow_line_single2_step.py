from __future__ import annotations

import math
from enum import Enum, auto
from typing import TYPE_CHECKING

from libstp import IRSensor, dsl
from libstp.motion import LinearAxis, LinearMotion, LinearMotionConfig, TurnConfig, TurnMotion
from libstp.step.motion.motion_step import MotionStep

if TYPE_CHECKING:
    from libstp.robot.api import GenericRobot


class _Phase(Enum):
    SEARCH_FIRST_BLACK = auto()
    MEASURE_X1 = auto()
    DRIVE_DELTA = auto()
    TURN_LEFT_BETA = auto()
    SEARCH_SECOND_BLACK = auto()
    MEASURE_X2 = auto()
    FINAL_TURN = auto()


@dsl(hidden=True)
class FollowLineSingle2Step(MotionStep):
    def __init__(
        self,
        sensor: IRSensor,
        delta_s_cm: float,
        beta_deg: float = 15.0,
        speed: float = 0.4,
        turn_speed: float = 0.35,
        search_distance_cm: float = 60.0,
    ):
        super().__init__()
        self._sensor = sensor
        self._delta_s_cm = delta_s_cm
        self._beta_deg = beta_deg
        self._speed = speed
        self._turn_speed = turn_speed
        self._search_distance_cm = search_distance_cm

        self._phase = _Phase.SEARCH_FIRST_BLACK
        self._motion: LinearMotion | TurnMotion | None = None
        self._measure_start_m = 0.0
        self._x1_cm = 0.0
        self._x2_cm = 0.0
        self._t_cm = 0.0
        self._alpha1_rad = 0.0
        self._alpha2_rad = 0.0
        self._started_on_black = False

    def _generate_signature(self) -> str:
        return (
            "FollowLineSingle2("
            f"delta_s={self._delta_s_cm:.1f}, beta={self._beta_deg:.1f}, "
            f"speed={self._speed:.2f}, turn_speed={self._turn_speed:.2f})"
        )

    def _make_linear(self, robot: "GenericRobot", distance_cm: float) -> LinearMotion:
        cfg = LinearMotionConfig()
        cfg.axis = LinearAxis.Forward
        cfg.distance_m = distance_cm / 100.0
        cfg.speed_scale = self._speed
        motion = LinearMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        motion.start()
        return motion

    def _make_turn(self, robot: "GenericRobot", angle_rad: float) -> TurnMotion:
        cfg = TurnConfig()
        cfg.target_angle_rad = angle_rad
        cfg.speed_scale = self._turn_speed
        motion = TurnMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        motion.start()
        return motion

    def _start_turn_deg(self, robot: "GenericRobot", angle_deg: float) -> TurnMotion:
        return self._make_turn(robot, math.radians(angle_deg))

    def _position_m(self) -> float:
        assert isinstance(self._motion, LinearMotion)
        telemetry = self._motion.get_telemetry()
        if isinstance(telemetry, list):
            if not telemetry:
                return 0.0
            return telemetry[-1].position_m
        return telemetry.position_m

    @staticmethod
    def _clamp_unit(value: float) -> float:
        return max(-1.0, min(1.0, value))

    def _fail(self, message: str) -> bool:
        self.error(message)
        return True

    def on_start(self, robot: "GenericRobot") -> None:
        if self._delta_s_cm < 0.0:
            raise ValueError("delta_s_cm must be non-negative")
        if self._search_distance_cm <= 0.0:
            raise ValueError("search_distance_cm must be positive")

        self._started_on_black = self._sensor.isOnBlack()
        self._phase = _Phase.SEARCH_FIRST_BLACK
        self._motion = self._make_linear(robot, self._search_distance_cm)
        self.info(
            f"Searching first tape crossing with search_distance={self._search_distance_cm:.1f} cm"
        )
        if self._started_on_black:
            self.info("Sensor started on black; waiting for white before starting X1")

    def on_update(self, robot: "GenericRobot", dt: float) -> bool:
        assert self._motion is not None
        self._motion.update(dt)

        if self._phase == _Phase.SEARCH_FIRST_BLACK:
            if self._started_on_black:
                if self._sensor.isOnWhite():
                    self._started_on_black = False
                    self.info("Detected white after start-on-black; now waiting for first black edge")
                elif self._motion.is_finished():
                    return self._fail("Sensor started on black and never reached white within search_distance_cm")
                return False

            if self._sensor.isOnBlack():
                self._motion = self._make_linear(robot, self._search_distance_cm)
                self._measure_start_m = self._position_m()
                self._phase = _Phase.MEASURE_X1
                self.info("Detected first black edge; measuring X1")
            elif self._motion.is_finished():
                return self._fail("Did not find the first black tape within search_distance_cm")
            return False

        if self._phase == _Phase.MEASURE_X1:
            if self._sensor.isOnWhite():
                self._x1_cm = abs(self._position_m() - self._measure_start_m) * 100.0
                self.info(f"Measured X1={self._x1_cm:.2f} cm")
                self._motion = self._make_linear(robot, self._delta_s_cm)
                self._phase = _Phase.DRIVE_DELTA
            elif self._motion.is_finished():
                return self._fail(
                    "Tape did not end while measuring X1. Increase search_distance_cm or check IR calibration."
                )
            return False

        if self._phase == _Phase.DRIVE_DELTA:
            if self._motion.is_finished():
                self._motion = self._make_turn(robot, math.radians(self._beta_deg))
                self._phase = _Phase.TURN_LEFT_BETA
                self.info(f"Driving delta complete; turning left by beta={self._beta_deg:.2f} deg")
            return False

        if self._phase == _Phase.TURN_LEFT_BETA:
            if self._motion.is_finished():
                self._motion = self._make_linear(robot, -self._search_distance_cm)
                self._phase = _Phase.SEARCH_SECOND_BLACK
                self.info("Beta turn complete; searching second tape crossing while reversing")
            return False

        if self._phase == _Phase.SEARCH_SECOND_BLACK:
            if self._sensor.isOnBlack():
                self._motion = self._make_linear(robot, -self._search_distance_cm)
                self._measure_start_m = self._position_m()
                self._phase = _Phase.MEASURE_X2
                self.info("Detected second black edge; measuring X2")
            elif self._motion.is_finished():
                return self._fail("Did not find the second black tape within search_distance_cm")
            return False

        if self._phase == _Phase.MEASURE_X2:
            if self._sensor.isOnWhite():
                self._x2_cm = abs(self._position_m() - self._measure_start_m) * 100.0

                if self._x1_cm <= 0.0 or self._x2_cm <= 0.0:
                    return self._fail("Measured X1/X2 must both be positive")

                beta_rad = math.radians(self._beta_deg)
                denominator = math.sqrt(
                    self._x1_cm ** 2
                    + self._x2_cm ** 2
                    - 2.0 * self._x1_cm * self._x2_cm * math.cos(beta_rad)
                )
                if denominator <= 0.0:
                    return self._fail("Computed denominator for T is invalid")

                self._t_cm = (
                    self._x1_cm * self._x2_cm * math.sin(beta_rad)
                ) / denominator

                if self._t_cm <= 0.0:
                    return self._fail("Computed tape width T is invalid")

                self._alpha1_rad = math.acos(self._clamp_unit(self._t_cm / self._x1_cm))
                self._alpha2_rad = math.acos(self._clamp_unit(self._t_cm / self._x2_cm))

                alpha1_deg = math.degrees(self._alpha1_rad)
                alpha2_deg = math.degrees(self._alpha2_rad)
                self.info(
                    f"Debug: X1={self._x1_cm:.2f} cm, X2={self._x2_cm:.2f} cm"
                )
                self.info(
                    f"Debug: T={self._t_cm:.2f} cm, alpha1={alpha1_deg:.2f} deg, alpha2={alpha2_deg:.2f} deg"
                )

                if self._alpha1_rad > self._alpha2_rad:
                    correction_deg = ((alpha1_deg + alpha2_deg + self._beta_deg) / 2.0) - self._beta_deg
                    direction = "left" if correction_deg >= 0.0 else "right"
                    self.info(
                        f"Debug: final correction angle={abs(correction_deg):.2f} deg, direction={direction}"
                    )
                    self._motion = self._start_turn_deg(robot, correction_deg)
                else:
                    correction_deg = ((alpha1_deg + alpha2_deg - self._beta_deg) / 2.0) + self._beta_deg
                    direction = "right" if correction_deg >= 0.0 else "left"
                    self.info(
                        f"Debug: final correction angle={abs(correction_deg):.2f} deg, direction={direction}"
                    )
                    self._motion = self._start_turn_deg(robot, -correction_deg)

                self._phase = _Phase.FINAL_TURN
            elif self._motion.is_finished():
                return self._fail(
                    "Tape did not end while measuring X2. Increase search_distance_cm or check IR calibration."
                )
            return False

        return self._motion.is_finished()


@dsl(tags=["motion", "sensor"])
def follow_line_single2(
    sensor: IRSensor,
    delta_s_cm: float,
    beta_deg: float = 15.0,
    speed: float = 0.4,
    turn_speed: float = 0.35,
    search_distance_cm: float = 60.0,
) -> FollowLineSingle2Step:
    """Measure a tape crossing twice and compute the heading correction.

    The robot:
    1. drives forward until the sensor crosses black and then back to white,
    2. measures that black interval as X1,
    3. drives forward by delta_s_cm,
    4. turns left by beta_deg,
    5. drives backward across the tape and measures the black interval as X2,
    6. computes T, alpha1, alpha2, and finally turns left or right.
    """
    return FollowLineSingle2Step(
        sensor=sensor,
        delta_s_cm=delta_s_cm,
        beta_deg=beta_deg,
        speed=speed,
        turn_speed=turn_speed,
        search_distance_cm=search_distance_cm,
    )
