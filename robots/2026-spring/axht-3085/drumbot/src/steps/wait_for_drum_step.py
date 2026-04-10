"""Wait until the camera detects a drum (any color), then close after a short delay."""

import asyncio
import time

from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.hardware.defs import Defs
from src.service.color_detection_service import ColorDetectionService
from src.service.sorting_service import SortingService

BLOCK_ANGLE = 82       # servo angle to block the drum
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

        # Clear stale detection first — start detecting immediately
        color_service.reset()

        learned_timeout = sorting_service.learned_timeout

        if self.checkpoint is not None:
            elapsed = robot.synchronizer.get_time()
            remaining = max(self.checkpoint - elapsed, 0)
            self.info(
                f"Waiting for drum (checkpoint in {remaining:.3f}s, "
                f"learned_timeout={learned_timeout:.3f}s, close_delay={self.close_delay:.3f}s)"
            )

            t0 = time.monotonic()

            # Start detecting immediately — if camera sees something, react now
            if remaining > 0:
                detected = await color_service.wait_for_color(remaining)
            else:
                detected = False

            if not detected:
                # Checkpoint reached without detection — use learned timeout as fallback
                detected = await color_service.wait_for_color(learned_timeout)
        else:
            self.info(f"Waiting for drum (timeout={learned_timeout:.3f}s, close_delay={self.close_delay:.3f}s)")
            t0 = time.monotonic()
            detected = await color_service.wait_for_color(learned_timeout)

        if not detected:
            # One brief extra window
            detected = await color_service.wait_for_color(0.050)

        wall_delta = time.monotonic() - t0

        if detected:
            # Record delta relative to checkpoint — only post-checkpoint
            # lateness matters for learning the fallback timeout.
            if self.checkpoint is not None:
                checkpoint_relative = wall_delta - remaining
                sorting_service.record_detection_delta(max(0.0, checkpoint_relative))
            else:
                sorting_service.record_detection_delta(wall_delta)
            color_service.lock_color()
            self.info(f"Drum detected at {wall_delta:.3f}s — closing servo in {self.close_delay:.3f}s")
            await asyncio.sleep(self.close_delay)
        else:
            self.warn(
                f"Timeout ({learned_timeout:.3f}s) waiting for drum — "
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
