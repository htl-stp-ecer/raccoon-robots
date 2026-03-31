import time

from libstp import GenericRobot, dsl
from libstp.step import Step

from src.service.color_detection_service import ColorDetectionService
from src.service.drum_motor_service import DrumMotorService
from src.service.sorting_service import SortingService

DEADLINE_WARNING_SECS = 6.0

# Shared timestamp set by BlockTimerStartStep, checked by BlockTimerCheckStep
_block_start_time: float = 0.0


@dsl(hidden=True)
class SortIntoSlotStep(Step):
    """Detect drum color, compute target slot, rotate revolver there."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        color_service = robot.get_service(ColorDetectionService)
        sorting_service = robot.get_service(SortingService)
        drum_service = robot.get_service(DrumMotorService)

        color = await color_service.detect_color()
        if color is None:
            color = sorting_service.guess_color()
            self.warn(f"Camera failed — guessed color: {color}")
        target = sorting_service.assign_slot(color)
        await drum_service.go_to_pocket(target, precise=False)


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

        empty = sorting_service.nearest_empty_slot(drum_service.current_pocket)
        drum_service.info(f"Moving to empty slot {empty} before opening pusher")
        await drum_service.go_to_pocket(empty, precise=False)


@dsl(hidden=True)
class AdvanceToMidpointStep(Step):
    """Advance one pocket so the opening sits on the divider, preventing drums from falling out."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        drum_service = robot.get_service(DrumMotorService)
        drum_service.info("Moving to midpoint (cover opening during lift)")
        await drum_service.move_to_midpoint()


@dsl(hidden=True)
class RetreatFromMidpointStep(Step):
    """Retreat one pocket back from midpoint to proper slot alignment."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        drum_service = robot.get_service(DrumMotorService)
        drum_service.info("Returning from midpoint (restore slot alignment)")
        await drum_service.move_from_midpoint()


@dsl()
def advance_to_midpoint() -> AdvanceToMidpointStep:
    """Advance one pocket to midpoint to prevent drums from falling out during lift."""
    return AdvanceToMidpointStep()


@dsl()
def retreat_from_midpoint() -> RetreatFromMidpointStep:
    """Retreat one pocket from midpoint back to proper slot alignment."""
    return RetreatFromMidpointStep()


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
