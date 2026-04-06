import asyncio
import math
from libstp import *

from src.hardware.defs import Defs


@dsl_step(tags=["sensor"])
class LineCrossDetectingTurn(Step):
    """Turns to a heading while monitoring an IR sensor for a black-line crossing.

    Starts tracking after the robot has rotated past *tracking_start_deg*.
    After the turn, :attr:`crossed_line` indicates whether the sensor saw
    black during the second half of the rotation.
    """

    def __init__(
        self,
        target_heading: float = 90,
        speed: float = 1.0,
        tracking_start_deg: float = 45,
        sensor: IRSensor | None = None,
    ):
        super().__init__()
        self.target_heading = target_heading
        self.speed = speed
        self.tracking_start_deg = tracking_start_deg
        self.sensor = sensor or Defs.rear.right
        self._crossed_line = False

    async def _execute_step(self, robot) -> None:
        self._crossed_line = False
        sampling = True
        start_heading_deg = math.degrees(robot.defs.imu.get_heading())

        async def sample_loop():
            while sampling:
                heading_deg = math.degrees(robot.defs.imu.get_heading())
                rotated = abs(heading_deg - start_heading_deg)
                # Wrap to [0, 360)
                rotated = rotated % 360
                if rotated >= self.tracking_start_deg:
                    if self.sensor.isOnBlack():
                        self._crossed_line = True
                await asyncio.sleep(0.01)  # ~100 Hz

        turn_step = turn_to_heading_right(self.target_heading, self.speed)

        sample_task = asyncio.create_task(sample_loop())
        try:
            await turn_step._execute_step(robot)
        finally:
            sampling = False
            await sample_task

    @property
    def crossed_line(self) -> bool:
        """True if the sensor detected black after passing *tracking_start_deg*."""
        return self._crossed_line

    def required_resources(self) -> frozenset[str]:
        return frozenset({})
