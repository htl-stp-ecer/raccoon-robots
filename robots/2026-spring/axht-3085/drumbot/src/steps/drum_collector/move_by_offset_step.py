from libstp import GenericRobot, Step, dsl

from src.service.drum_motor_service import DrumMotorService, FULL_VELOCITY, SAMPLE_INTERVAL

import asyncio


@dsl(hidden=True)
class MoveDrumMotorByOffsetStep(Step):
    def __init__(self, offset: int):
        super().__init__()
        self.offset = offset

    async def _execute_step(self, robot: "GenericRobot") -> None:
        service = robot.get_service(DrumMotorService)
        target = service.motor.get_position() + self.offset
        service.motor.move_to_position(FULL_VELOCITY, target)
        while not service.motor.is_done():
            await asyncio.sleep(SAMPLE_INTERVAL)

@dsl
def move_drum_motor_by_offset(offset: int) -> MoveDrumMotorByOffsetStep:
    """Move the drum motor by a relative offset (positive or negative)."""
    return MoveDrumMotorByOffsetStep(offset=offset)
