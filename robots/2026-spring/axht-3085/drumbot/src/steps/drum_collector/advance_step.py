from raccoon import GenericRobot, dsl
from raccoon.step import Step
from raccoon.step.motion.path.passes import velocity_profile

from src.service.drum_motor_service import DrumMotorService


@dsl(hidden=True)
class DrumAdvanceStep(Step):
    def __init__(self, count: int = 1, velocity_factor: float = 1.0):
        super().__init__()
        self.count = count
        self.velocity_factor = velocity_factor

    async def _execute_step(self, robot: "GenericRobot") -> None:
        service: DrumMotorService = robot.get_service(DrumMotorService)
        await service.advance(self.count, velocity_factor=self.velocity_factor)





@dsl()
def drum_advance(count: int = 1, velocity_factor: float = 1.0) -> DrumAdvanceStep:
    """Advance the drum forward by count pockets."""
    return DrumAdvanceStep(count=count, velocity_factor=velocity_factor)
