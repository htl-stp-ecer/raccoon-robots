"""Wait until the camera detects a drum (any color), then close after a short delay."""

import asyncio
import time

from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.hardware.defs import Defs
from src.service.color_detection_service import ColorDetectionService
from src.service.sorting_service import SortingService

CLOSE_DELAY = 0.1     # seconds to let the drum roll fully into position after detection

# If a drum is "detected" this fast after we start looking, the color was
# already in view before waiting began — i.e. the previous drum never left the
# camera and is stuck against the blocker. A genuine fresh drop takes ~0.4-0.5s
# to roll into view (see run logs), so anything below this is a stuck drum, not
# a new one.
INSTANT_STUCK_THRESHOLD = 0.1  # seconds


class DrumStuckError(Exception):
    """Raised when a drum is detected suspiciously fast (color already in view).

    Signals that a previous drum never left the camera and is stuck. Collection
    should stop, but the revolver motor is mechanically fine — so, unlike
    ``MotorStalledError``, this does NOT lock or brake the motor.
    """

    def __init__(self, delta: float) -> None:
        super().__init__(f"drum detected instantly ({delta * 1000:.0f}ms)")
        self.delta = delta


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
            detected = await color_service.wait_for_color(0.200)

        wall_delta = time.monotonic() - t0

        if detected:
            # Record delta relative to checkpoint — only post-checkpoint
            # lateness matters for learning the fallback timeout.
            if self.checkpoint is not None:
                checkpoint_relative = wall_delta - remaining
                sorting_service.record_detection_delta(max(0.0, checkpoint_relative))
            else:
                sorting_service.record_detection_delta(wall_delta)
            # Instant "detection" means the color was already in view before we
            # started waiting — the previous drum is stuck, not a new one. Bail
            # out so collection stops (motor stays free; caller handles it).
            if wall_delta < INSTANT_STUCK_THRESHOLD:
                self.warn(
                    f"Drum detected instantly at {wall_delta * 1000:.0f}ms "
                    f"(< {INSTANT_STUCK_THRESHOLD * 1000:.0f}ms) — drum stuck, not a fresh drop"
                )
                raise DrumStuckError(wall_delta)
            color_service.lock_color()
            self.info(f"Drum detected at {wall_delta:.3f}s — closing servo in {self.close_delay:.3f}s")
            await asyncio.sleep(self.close_delay)
        else:
            self.warn(
                f"Timeout ({learned_timeout:.3f}s) waiting for drum — "
                f"closing anyway based on learned timing"
            )
            color_service.record_miss()
            color_service.lock_color()

        Defs.drum_pusher_servo.device.set_position(Defs.drum_pusher_servo.block_angle.value)


@dsl()
def wait_for_drum(
    checkpoint: float | None = None,
    close_delay: float = CLOSE_DELAY,
) -> WaitForDrumStep:
    """Wait until the camera sees a drum, optionally after a checkpoint."""
    return WaitForDrumStep(checkpoint=checkpoint, close_delay=close_delay)
