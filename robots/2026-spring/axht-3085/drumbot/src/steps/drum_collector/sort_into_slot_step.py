import time

from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.service.color_detection_service import ColorDetectionService
from src.service.drum_motor_service import DrumMotorService, MotorStalledError, NUM_POCKETS
from src.service.sorting_service import SortingService

DEADLINE_WARNING_SECS = 6.0

# Physical slot index where the ejection hole is located.
EJECT_HOLE_SLOT = 5

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
        # Collect filled slots *before* this assignment (target not yet occupied,
        # so it is safe to pass through it if needed — but it won't be intermediate).
        filled = {i for i, s in enumerate(sorting_service.slots) if s is not None and i != target}
        await drum_service.go_to_pocket_via_gap(target, filled, precise=False)


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
    """Move revolver to a strategically chosen empty slot so opening the pusher is safe.

    Instead of the *nearest* empty slot, pick the centre of the gap between
    the two colour fronts so the next drum — regardless of colour — is
    reachable via a short, unblocked path.
    """

    async def _execute_step(self, robot: "GenericRobot") -> None:
        sorting_service = robot.get_service(SortingService)
        drum_service = robot.get_service(DrumMotorService)

        empty = sorting_service.strategic_empty_slot(drum_service.current_pocket)
        filled = {i for i, s in enumerate(sorting_service.slots) if s is not None}
        drum_service.info(f"Moving to strategic empty slot {empty} before opening pusher")
        await drum_service.go_to_pocket_via_gap(empty, filled, precise=False)


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


@dsl(hidden=True)
class EjectNearestColorStep(Step):
    """Sweep through all slots of the nearest color group in one continuous motion."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        sorting_service = robot.get_service(SortingService)
        drum_service = robot.get_service(DrumMotorService)

        blue = sorting_service.blue_slots
        pink = sorting_service.pink_slots

        if not blue and not pink:
            drum_service.warn("No drums assigned yet — nothing to eject")
            return

        def nearest_dist(slots):
            return min(min(abs(EJECT_HOLE_SLOT - s), NUM_POCKETS - abs(EJECT_HOLE_SLOT - s)) for s in slots) if slots else float("inf")

        if not pink or nearest_dist(blue) <= nearest_dist(pink):
            slots = blue
            color = "blue"
        else:
            slots = pink
            color = "pink"

        try:
            # Retreat from midpoint first to get clean slot alignment.
            if drum_service.at_midpoint:
                drum_service.info("Retreating from midpoint before ejection")
                await drum_service.move_from_midpoint()

            # Choose the closer end of the group as the starting point, then sweep
            # toward the other end — minimises total travel before ejection begins.
            # Uses ring_contiguous_endpoints so wrapping groups (e.g. blue at
            # {0, 6, 7, 8}) are handled correctly.
            def ring_dist(a: int, b: int) -> int:
                d = abs(a - b)
                return min(d, NUM_POCKETS - d)

            cur = drum_service.current_pocket
            start, end = sorting_service.ring_contiguous_endpoints(slots)

            if ring_dist(cur, start) <= ring_dist(cur, end):
                start_slot = (start - 1) % NUM_POCKETS  # one before start; advance through start..end
                forward = True
            else:
                start_slot = (end + 1) % NUM_POCKETS  # one after end; retreat through end..start
                forward = False


            pockets_to_eject = len(slots)
            drum_service.info(
                f"Ejecting {color}: go to slot {start_slot}, "
                f"then sweep {'forward' if forward else 'backward'} "
                f"{pockets_to_eject} pocket(s)"
            )
            await drum_service.go_to_pocket(start_slot, precise=False)
            for _ in range(pockets_to_eject):
                if forward:
                    await drum_service.advance(1)
                else:
                    await drum_service.retreat(1)

            # Final nudge: the last drum has no "next advance" to dislodge it if it
            # sits at the eject hole without falling. move_to_midpoint() pushes 1/3
            # pocket forward — enough to clear a stuck drum, too short to reach the
            # adjacent slot. It includes stall detection + retry internally.
            drum_service.info("Final nudge: pushing last drum through eject hole")
            try:
                await drum_service.move_to_midpoint()
            except MotorStalledError:
                drum_service.warn("Final nudge stalled — last drum may still be at eject hole")

            # Mark ejected slots as empty so the next eject call picks the other color.
            for s in slots:
                sorting_service.slots[s] = None
            drum_service.info(f"Cleared {color} slots {slots} → {sorting_service.slots}")
        except MotorStalledError as e:
            # Eject must never kill the program — mark this attempt as flawed and
            # let the mission sequence continue. Retries (self.stall_retries) are
            # exhausted by the time we get here.
            drum_service.warn(
                f"Eject ({color}) FAILED after retries — marking attempt as flawed and continuing: {e}"
            )
        finally:
            # Passive brake: H-bridge shorts the leads for electrical braking.
            # No active hold needed while the robot drives to the next pipe.
            drum_service.motor.set_speed(0)


@dsl()
def eject_nearest_color() -> EjectNearestColorStep:
    """Navigate to each slot of the nearest color group and eject all four drums."""
    return EjectNearestColorStep()


@dsl(hidden=True)
class GoToEmptySlotPlusOneStep(Step):
    """Move revolver to the nearest empty slot + 1 pocket."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        sorting_service = robot.get_service(SortingService)
        drum_service = robot.get_service(DrumMotorService)

        empty = sorting_service.nearest_empty_slot(drum_service.current_pocket)
        target = (empty - 1) % NUM_POCKETS
        drum_service.info(f"Moving to empty slot {empty} + 1 = pocket {target}")
        await drum_service.go_to_pocket(target, precise=False)


@dsl()
def go_to_empty_slot() -> GoToEmptySlotStep:
    """Move revolver to nearest empty slot (safe to open pusher)."""
    return GoToEmptySlotStep()


@dsl()
def go_to_empty_slot_plus_one() -> GoToEmptySlotPlusOneStep:
    """Move revolver to nearest empty slot + 1 pocket."""
    return GoToEmptySlotPlusOneStep()


@dsl()
def block_timer_start() -> BlockTimerStartStep:
    """Start timing a collection block."""
    return BlockTimerStartStep()


@dsl()
def block_timer_check(drum_number: int) -> BlockTimerCheckStep:
    """Check and log elapsed time for a collection block."""
    return BlockTimerCheckStep(drum_number=drum_number)
