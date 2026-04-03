"""Wait until the camera detects a drum (any color), then close after a short delay."""

import asyncio
import time

from libstp import GenericRobot, dsl
from libstp.step import Step

from src.hardware.defs import Defs
from src.service.color_detection_service import ColorDetectionService
from src.service.sorting_service import SortingService

BLOCK_ANGLE = 40       # servo angle to block the drum
CLOSE_DELAY = 0.0     # seconds to wait after detection before closing servo


@dsl(hidden=True)
class WaitForDrumStep(Step):
    """Wait for the background detection loop to spot a drum.

    Uses an event-based approach: the detection thread signals as soon
    as it sees a color, and we await that event with the learned timeout.
    No polling, no pausing the detection loop.

    Closes the pusher servo after CLOSE_DELAY seconds to let the drum
    roll fully into position before blocking.
    """

    def __init__(
        self,
        checkpoint: float | None = None,
        close_delay: float = CLOSE_DELAY,
    ) -> None:
        super().__init__()
        self.checkpoint = checkpoint
        self.close_delay = close_delay

    async def _execute_step(self, robot: GenericRobot) -> None:
        color_service = robot.get_service(ColorDetectionService)
        sorting_service = robot.get_service(SortingService)

        # Wait until the checkpoint so we don't react to stale data
        if self.checkpoint is not None:
            await robot.synchronizer.wait_until_checkpoint(self.checkpoint)

        # Clear stale detection — the background loop keeps running
        color_service.reset()

        timeout = sorting_service.learned_timeout
        self.info(f"Waiting for drum (timeout={timeout:.3f}s, close_delay={self.close_delay:.3f}s)")

        t0 = time.monotonic()
        detected = await color_service.wait_for_color(timeout)

        if not detected:
            # Drum may have arrived just after timeout — one brief extra window
            detected = await color_service.wait_for_color(0.050)

        detection_delta = time.monotonic() - t0

        if detected:
            sorting_service.record_detection_delta(detection_delta)
            color_service.lock_color()
            self.info(f"Drum detected at {detection_delta:.3f}s — closing servo in {self.close_delay:.3f}s")
            await asyncio.sleep(self.close_delay)
        else:
            self.warn(
                f"Timeout ({timeout:.3f}s) waiting for drum — "
                f"closing anyway based on learned timing"
            )
            color_service.lock_color()

        Defs.drum_pusher_servo.set_position(BLOCK_ANGLE)


@dsl()
def wait_for_drum(
    checkpoint: float | None = None,
    close_delay: float = CLOSE_DELAY,
) -> WaitForDrumStep:
    """Wait until the camera sees a drum, optionally after a checkpoint."""
    return WaitForDrumStep(checkpoint=checkpoint, close_delay=close_delay)
