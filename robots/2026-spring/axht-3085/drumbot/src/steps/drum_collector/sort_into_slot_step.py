import time

from libstp import GenericRobot, dsl
from libstp.step import Step

from src.service.color_detection_service import ColorDetectionService
from src.service.drum_motor_service import DrumMotorService
from src.service.sorting_service import SortingService

DEADLINE_WARNING_SECS = 6.0

# Shared timestamp set by BlockTimerStartStep, checked by BlockTimerCheckStep
_block_start_time: float = 0.0


OFFSET_FORWARD_TICKS = 0    # ticks offset after forward travel
OFFSET_BACKWARD_TICKS = -40000   # ticks offset after backward travel
OFFSET_VELOCITY = 1500         # firmware PID velocity for offset


@dsl(hidden=True)
class SortIntoSlotStep(Step):
    """Detect drum color, compute target slot, rotate revolver there, apply offset."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        color_service = robot.get_service(ColorDetectionService)
        sorting_service = robot.get_service(SortingService)
        drum_service = robot.get_service(DrumMotorService)

        color = await color_service.detect_color()
        target = sorting_service.assign_slot(color)
        direction = await drum_service.go_to(target)

        # Position-based offset nudge
        if direction == "forward":
            offset = OFFSET_FORWARD_TICKS
        elif direction == "backward":
            offset = OFFSET_BACKWARD_TICKS
        else:
            offset = 0

        if offset != 0:
            drum_service.info(f"Applying offset: {offset} ticks, direction={direction}")
            await drum_service.add_offset(offset, velocity=400)


@dsl(hidden=True)
class BlockTimerStartStep(Step):
    """Record the start time of a collection block."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        global _block_start_time
        _block_start_time = time.monotonic()


@dsl(hidden=True)
class BlockTimerCheckStep(Step):
    """Check elapsed time since block start and warn if over deadline."""

    def __init__(self, drum_number: int):
        super().__init__()
        self.drum_number = drum_number

    async def _execute_step(self, robot: "GenericRobot") -> None:
        elapsed = time.monotonic() - _block_start_time
        drum_service = robot.get_service(DrumMotorService)
        drum_service.info(f"Block drum #{self.drum_number} complete: {elapsed:.2f}s")
        if elapsed > DEADLINE_WARNING_SECS:
            drum_service.warn(
                f"TIMING CRITICAL: drum #{self.drum_number} block took {elapsed:.2f}s "
                f"(> {DEADLINE_WARNING_SECS}s) — next drum checkpoint at risk!",
            )


@dsl(hidden=True)
class GoToEmptySlotStep(Step):
    """Move revolver to the nearest empty slot so opening the pusher is safe."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        sorting_service = robot.get_service(SortingService)
        drum_service = robot.get_service(DrumMotorService)

        empty = sorting_service.nearest_empty_slot(drum_service.current_index)
        drum_service.info(f"Moving to empty slot {empty} before opening pusher")
        direction = await drum_service.go_to(empty)

        # Position-based offset so the empty slot is centered under the pipe
        if direction == "forward":
            offset = OFFSET_FORWARD_TICKS
        elif direction == "backward":
            offset = OFFSET_BACKWARD_TICKS
        else:
            offset = 0

        if offset != 0:
            drum_service.info(f"Empty slot offset: {offset} ticks, direction={direction}")
            await drum_service.add_offset(offset, velocity=1500)


@dsl()
def sort_into_slot() -> SortIntoSlotStep:
    """Detect color and sort the current drum into the correct slot."""
    return SortIntoSlotStep()


@dsl()
def go_to_empty_slot() -> GoToEmptySlotStep:
    """Move revolver to nearest empty slot (safe to open pusher)."""
    return GoToEmptySlotStep()


@dsl()
def block_timer_start() -> BlockTimerStartStep:
    """Start timing a collection block."""
    return BlockTimerStartStep()


@dsl()
def block_timer_check(drum_number: int) -> BlockTimerCheckStep:
    """Check and log elapsed time for a collection block."""
    return BlockTimerCheckStep(drum_number=drum_number)
