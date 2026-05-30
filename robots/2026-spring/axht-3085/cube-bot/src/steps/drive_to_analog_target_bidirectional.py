"""Drive forward OR backward until an analog sensor crosses its calibrated target.

This is a modified copy of the built-in ``drive_to_analog_target()`` step that
adds an explicit ``direction`` parameter ("forward" or "backward"). The built-in
step infers direction automatically from the current reading vs. the calibrated
target; this version lets you force it.

It is fully compatible with ``calibrate_analog_sensor()`` — it loads the same
stored reference value from the same CalibrationStore section/key, so no change
to the calibration flow is needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from raccoon.step.motion.motion_step import MotionStep

if TYPE_CHECKING:
    from raccoon.hal import AnalogSensor
    from raccoon.robot.api import GenericRobot


class DriveToAnalogTargetBidirectional(MotionStep):
    """Drive in an explicit direction until an analog sensor reaches its target.

    Args:
        sensor: The AnalogSensor to monitor.
        direction: "forward" or "backward". Overrides the auto-direction logic
            from the original step.
        speed: Drive speed fraction (0.0-1.0).
        set_name: Which stored calibration point to target (default "default").
        timeout_cm: Safety backstop distance in cm. None = use the 5 m sentinel.
    """

    _SENTINEL_DISTANCE_M = 5.0  # 5 m backstop when no timeout_cm given

    def __init__(
        self,
        sensor: "AnalogSensor",
        direction: str = "forward",
        speed: float = 0.3,
        set_name: str = "default",
        timeout_cm: float | None = None,
    ) -> None:
        super().__init__()
        if not (0.0 < speed <= 1.0):
            msg = f"speed must be in (0.0, 1.0], got {speed}"
            raise ValueError(msg)
        if direction not in ("forward", "backward"):
            msg = f"direction must be 'forward' or 'backward', got '{direction}'"
            raise ValueError(msg)
        self._sensor = sensor
        self._direction = direction
        self._speed = speed
        self._set_name = set_name
        self._timeout_cm = timeout_cm
        self._target_value: float | None = None
        self._driving_forward: bool = direction == "forward"
        # Set in on_start: True when the starting reading is below the target,
        # so we stop once it rises to/through the target (and vice versa). This
        # is decided from the reading, NOT from drive direction, otherwise a
        # forced direction can leave the stop condition already satisfied at
        # start and the step finishes instantly without moving.
        self._approach_from_below: bool = True
        self._motion = None

    def _generate_signature(self) -> str:
        timeout_str = f", timeout={self._timeout_cm}cm" if self._timeout_cm else ""
        return (
            f"DriveToAnalogTargetBidirectional(port={self._sensor.port}, "
            f"set={self._set_name!r}, dir={self._direction}, "
            f"speed={self._speed:.2f}{timeout_str})"
        )

    def on_start(self, robot: "GenericRobot") -> None:
        from raccoon.motion import LinearAxis, LinearMotion, LinearMotionConfig
        from raccoon.step.calibration.calibrate_analog_sensor import (
            ANALOG_SENSOR_STORE_SECTION,
            analog_sensor_store_key,
        )
        from raccoon.step.calibration.store import CalibrationStore

        store = CalibrationStore()
        key = analog_sensor_store_key(self._sensor, self._set_name)
        data = store.load(ANALOG_SENSOR_STORE_SECTION, key)
        if data is None:
            msg = (
                f"No analog sensor calibration found for port {self._sensor.port} "
                f"set '{self._set_name}'. "
                f"Run calibrate_analog_sensor() first."
            )
            raise RuntimeError(msg)

        self._target_value = float(data["target_value"])
        current = float(self._sensor.read())
        self._approach_from_below = current < self._target_value

        if current == self._target_value:
            self.warn(
                f"DriveToAnalogTargetBidirectional: starting reading {current:.1f} "
                f"already equals target {self._target_value:.1f} — step will not move."
            )

        self.debug(
            f"DriveToAnalogTargetBidirectional: port={self._sensor.port} "
            f"current={current:.1f} target={self._target_value:.1f} "
            f"direction={self._direction} "
            f"approach={'below' if self._approach_from_below else 'above'}"
        )

        distance_m = (
            self._timeout_cm / 100.0 if self._timeout_cm is not None else self._SENTINEL_DISTANCE_M
        )
        sign = 1.0 if self._driving_forward else -1.0

        config = LinearMotionConfig()
        config.axis = LinearAxis.Forward
        config.distance_m = sign * distance_m
        config.speed_scale = self._speed
        self._motion = LinearMotion(robot.drive, robot.odometry, robot.motion_pid_config, config)
        self._motion.start()

    def on_update(self, robot: "GenericRobot", dt: float) -> bool:
        current = float(self._sensor.read())
        # Stop when the reading crosses the target. Which comparison applies is
        # fixed by the starting side (see on_start), not the drive direction.
        if self._approach_from_below:
            if current >= self._target_value:
                return True
        elif current <= self._target_value:
            return True

        self._motion.update(dt)
        return self._motion.is_finished()


def drive_to_analog_target_bidirectional(
    sensor: "AnalogSensor",
    direction: str = "forward",
    speed: float = 0.3,
    set_name: str = "default",
    timeout_cm: float | None = None,
) -> DriveToAnalogTargetBidirectional:
    return DriveToAnalogTargetBidirectional(
        sensor=sensor,
        direction=direction,
        speed=speed,
        set_name=set_name,
        timeout_cm=timeout_cm,
    )
