import asyncio

from raccoon import *
from src.hardware.defs import Defs

CONE_PUSHER_MOTOR_MOVE_TIME = 0.4
CONE_PUSHER_MOTOR_MOVE_VELOCITY = -1300

class LowerConePusherStep(Step):
    def __init__(self):
        super().__init__()
        self._motor_ref = Defs.cone_pusher_motor

    async def _execute_step(self, robot):
        self._motor_ref.set_velocity(CONE_PUSHER_MOTOR_MOVE_VELOCITY)
        await asyncio.sleep(CONE_PUSHER_MOTOR_MOVE_TIME)
        self._motor_ref.brake()


@dsl()
def lower_cone_pusher():
    return LowerConePusherStep()
