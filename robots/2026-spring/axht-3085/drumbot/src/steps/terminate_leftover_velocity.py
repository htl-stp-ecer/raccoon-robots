from raccoon import *
from raccoon.foundation import ChassisVelocity

POSITION_HOLD_HZ = 50


@dsl(hidden=True)
class TerminateLeftoverVelocityStep(Step):
    def __init__(self):
        super().__init__()

    async def _execute_step(self, robot: "GenericRobot") -> None:
        robot.drive.set_velocity(ChassisVelocity(0.0, 0.0, 0.0))
        robot.drive.update(1.0 / POSITION_HOLD_HZ)
        robot.drive.hard_stop()


@dsl()
def terminate_leftover_velocity() -> TerminateLeftoverVelocityStep:
    return TerminateLeftoverVelocityStep()
