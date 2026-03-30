"""Wait until the camera detects a drum (any color), then return immediately."""

import asyncio
import time

from libstp import GenericRobot, dsl
from libstp.step import Step

from src.service.color_detection_service import ColorDetectionService


@dsl(hidden=True)
class WaitForDrumStep(Step):
    """Poll the camera until a color is detected, or timeout.

    Pauses the background detection loop and does direct single-frame
    analysis for minimum latency (~10-15ms per check). The background
    loop is resumed after detection or timeout.
    """

    def __init__(
        self,
        checkpoint: float | None = None,
        timeout: float = 5.0,
    ) -> None:
        super().__init__()
        self.checkpoint = checkpoint
        self.timeout = timeout

    async def _execute_step(self, robot: GenericRobot) -> None:
        color_service = robot.get_service(ColorDetectionService)

        # Wait until the checkpoint so we don't react to stale data
        if self.checkpoint is not None:
            await robot.synchronizer.wait_until_checkpoint(self.checkpoint)

        # Clear stale detection and pause background loop to free CPU
        color_service.reset()
        color_service.pause_detection()

        last_frame_id = 0
        try:
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                # Only analyze if there's a new frame
                frame_id = color_service._camera.total_frames
                if frame_id != last_frame_id:
                    last_frame_id = frame_id
                    color = color_service.detect_single_frame()
                    if color is not None:
                        with color_service._lock:
                            color_service._latest_color = color
                        color_service.lock_color()
                        return
                await asyncio.sleep(0.005)

            self.warn(
                f"Timeout ({self.timeout}s) waiting for drum — proceeding anyway"
            )
            color_service.lock_color()
        finally:
            color_service.resume_detection()


@dsl()
def wait_for_drum(
    checkpoint: float | None = None,
    timeout: float = 5.0,
) -> WaitForDrumStep:
    """Wait until the camera sees a drum, optionally after a checkpoint."""
    return WaitForDrumStep(checkpoint=checkpoint, timeout=timeout)
