"""Wait until the camera detects a drum (any color), then close immediately."""

import time

from libstp import GenericRobot, dsl
from libstp.step import Step

from src.hardware.defs import Defs
from src.service.color_detection_service import ColorDetectionService
from src.service.sorting_service import SortingService

BLOCK_ANGLE = 40  # servo angle to block the drum


@dsl(hidden=True)
class WaitForDrumStep(Step):
    """Wait for the background detection loop to spot a drum.

    Uses an event-based approach: the detection thread signals as soon
    as it sees a color, and we await that event with the learned timeout.
    No polling, no pausing the detection loop.

    Closes the pusher servo *immediately* on detection/timeout to
    prevent the drum from rolling back out.
    """

    def __init__(
        self,
        checkpoint: float | None = None,
    ) -> None:
        super().__init__()
        self.checkpoint = checkpoint

    async def _execute_step(self, robot: GenericRobot) -> None:
        color_service = robot.get_service(ColorDetectionService)
        sorting_service = robot.get_service(SortingService)

        # Wait until the checkpoint so we don't react to stale data
        if self.checkpoint is not None:
            await robot.synchronizer.wait_until_checkpoint(self.checkpoint)

        # Clear stale detection — the background loop keeps running
        color_service.reset()

        timeout = sorting_service.learned_timeout
        self.info(f"Waiting for drum (timeout={timeout:.3f}s)")

        t0 = time.monotonic()
        detected = await color_service.wait_for_color(timeout)

        # Close servo IMMEDIATELY
        Defs.drum_pusher_servo.set_position(BLOCK_ANGLE)

        if detected:
            delta = time.monotonic() - t0
            sorting_service.record_detection_delta(delta)
            color_service.lock_color()
        else:
            self.warn(
                f"Timeout ({timeout:.3f}s) waiting for drum — "
                f"closing anyway based on learned timing"
            )
            color_service.lock_color()


@dsl()
def wait_for_drum(
    checkpoint: float | None = None,
) -> WaitForDrumStep:
    """Wait until the camera sees a drum, optionally after a checkpoint."""
    return WaitForDrumStep(checkpoint=checkpoint)
