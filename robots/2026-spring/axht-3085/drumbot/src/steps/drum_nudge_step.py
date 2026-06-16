from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.service.drum_motor_service import DrumMotorService


@dsl(hidden=True)
class DrumNudgeStep(Step):
    """Physically advance one pocket without updating the pocket tracker.

    The IR stripe watcher still counts the crossing, so we restore the
    pre-move pocket index right after. Lets us bias the eject start by one
    pocket while EjectNearestColorStep's go_to_pocket(start_slot) stays a no-op.
    """

    async def _execute_step(self, robot: "GenericRobot") -> None:
        service: DrumMotorService = robot.get_service(DrumMotorService)
        before = service.current_pocket
        await service.retreat(1)
        service.reset_position(before)


@dsl()
def drum_nudge_backward() -> DrumNudgeStep:
    """Retreat one pocket physically but keep the tracker at the old pocket."""
    return DrumNudgeStep()
