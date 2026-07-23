"""Drive straight while sampling an analog sensor between two line crossings.

Useful for recording how an analog sensor (e.g. ``Defs.et_sensor``) behaves
over a known stretch of the field, so the data can be dumped into a CSV and
analyzed offline.

Sampling starts as soon as ``start_sensor`` (default ``Defs.front.right``)
sees black, and stops as soon as ``end_sensor`` (default ``Defs.rear.left``)
sees black afterwards. The drive itself also stops at that point.

Example::

    from src.steps.sample_analog_between_lines import sample_analog_between_lines

    sample_analog_between_lines(speed=0.3)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from raccoon import *

from src.hardware.defs import Defs

if TYPE_CHECKING:
    from raccoon.hal import AnalogSensor
    from raccoon.robot.api import GenericRobot
    from raccoon.sensor_ir import IRSensor


class SampleAnalogBetweenLines(Step):
    """Drive straight, logging (distance_cm, sensor_value) samples between two line crossings."""

    def __init__(
        self,
        direction: str = "forward",
        speed: float = 0.3,
        start_sensor: "IRSensor | None" = None,
        end_sensor: "IRSensor | None" = None,
        analog_sensor: "AnalogSensor | None" = None,
        threshold: float = 0.7,
        heading: float | None = None,
    ) -> None:
        super().__init__()
        if direction not in ("forward", "backward"):
            msg = f"direction must be 'forward' or 'backward', got '{direction}'"
            raise ValueError(msg)
        self._direction = direction
        self._speed = speed
        self._start_sensor = start_sensor or Defs.front.right
        self._end_sensor = end_sensor or Defs.rear.left
        self._analog_sensor = analog_sensor or Defs.et_sensor
        self._threshold = threshold
        self._heading = heading
        self.samples: list[tuple[float, float]] = []

    def required_resources(self) -> frozenset[str]:
        return frozenset()

    async def _execute_step(self, robot: "GenericRobot") -> None:
        self.samples = []
        running = True
        sampling = False
        start_path_m = 0.0

        async def sample_loop() -> None:
            nonlocal sampling, start_path_m
            while running:
                if not sampling and self._start_sensor.probabilityOfBlack() >= self._threshold:
                    sampling = True
                    start_path_m = robot.odometry.get_path_length()
                    self.info("sampling started")
                if sampling:
                    distance_cm = (robot.odometry.get_path_length() - start_path_m) * 100.0
                    value = float(self._analog_sensor.read())
                    self.samples.append((distance_cm, value))
                await asyncio.sleep(0.01)  # ~100 Hz

        stop_condition = on_black(self._start_sensor, self._threshold) + on_black(
            self._end_sensor, self._threshold
        )

        if self._direction == "forward":
            drive_step = drive_forward(speed=self._speed, until=stop_condition, heading=self._heading)
        else:
            drive_step = drive_backward(speed=self._speed, until=stop_condition, heading=self._heading)

        sample_task = asyncio.create_task(sample_loop())
        try:
            await drive_step._execute_step(robot)
        finally:
            running = False
            await sample_task

        self.info(f"sampling stopped, collected {len(self.samples)} samples")
        self.info("distance_cm,et_sensor")
        for distance_cm, value in self.samples:
            self.info(f"{distance_cm:.3f},{value:.1f}")


def sample_analog_between_lines(
    direction: str = "forward",
    speed: float = 0.3,
    start_sensor: "IRSensor | None" = None,
    end_sensor: "IRSensor | None" = None,
    analog_sensor: "AnalogSensor | None" = None,
    threshold: float = 0.7,
    heading: float | None = None,
) -> SampleAnalogBetweenLines:
    """Drive straight while sampling an analog sensor between two line crossings.

    Args:
        direction: "forward" or "backward".
        speed: Drive speed fraction (0.0-1.0].
        start_sensor: IR sensor whose black detection starts sampling.
            Defaults to ``Defs.front.right``.
        end_sensor: IR sensor whose black detection stops sampling (and the
            drive). Defaults to ``Defs.rear.left``.
        analog_sensor: Analog sensor to sample. Defaults to ``Defs.et_sensor``.
        threshold: ``probabilityOfBlack()`` threshold for line detection.
        heading: Optional absolute heading (degrees) to hold during the drive.

    After the step, ``.samples`` holds a list of ``(distance_cm, sensor_value)``
    tuples, and the same data is logged line-by-line as
    ``distance_cm,et_sensor`` for easy copy-paste into a CSV.
    """
    return SampleAnalogBetweenLines(
        direction=direction,
        speed=speed,
        start_sensor=start_sensor,
        end_sensor=end_sensor,
        analog_sensor=analog_sensor,
        threshold=threshold,
        heading=heading,
    )
