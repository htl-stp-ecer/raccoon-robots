from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.service.drum_motor_service import DrumMotorService, MotorStalledError


@dsl(hidden=True)
class DrumRetreatStep(Step):
    def __init__(self, count: int = 1):
        super().__init__()
        self.count = count

    async def _execute_step(self, robot: "GenericRobot") -> None:
        service = robot.get_service(DrumMotorService)
        # Enter the eject phase: this drops the emergency motor-lock so the
        # drums are still ejected even after a camera-stuck / timing emergency,
        # and picks the retry budget by cause (1 careful try for a genuinely
        # faulted motor, normal otherwise).
        service.begin_eject()
        try:
            await service.retreat(self.count)
        except MotorStalledError as e:
            # Eject must never kill the run — brake and continue. Retries are
            # already exhausted (per begin_eject's budget) by the time we land here.
            service.motor.brake()
            service.warn(f"Eject retreat({self.count}) stalled — braking and continuing: {e}")





@dsl()
def drum_retreat(count: int = 1) -> DrumRetreatStep:
    """Retreat the drum backward by count pockets."""
    return DrumRetreatStep(count=count)

