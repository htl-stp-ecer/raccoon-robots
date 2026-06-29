import os
from raccoon import *
from raccoon.foundation import ChassisVelocity

POSITION_HOLD_ENV = "DRUMBOT_NO_POSITION_HOLD"
POSITION_HOLD_VX = 0.12  # m/s forward push to hold the robot against the wall
POSITION_HOLD_HZ = 50


@dsl(hidden=True)
class SetPositionHoldVelocityStep(Step):
    def __init__(self):
        super().__init__()

    async def _execute_step(self, robot: "GenericRobot") -> None:
        if os.getenv(POSITION_HOLD_ENV):
            self.warn(f"{POSITION_HOLD_ENV} is set, ignoring call to set position hold velocity")
            return

        vel = ChassisVelocity(POSITION_HOLD_VX, 0.0, 0.0)
        robot.drive.set_velocity(vel)
        robot.drive.update(1.0 / POSITION_HOLD_HZ)


@dsl()
def set_position_hold_velocity() -> SetPositionHoldVelocityStep:
    return SetPositionHoldVelocityStep()
