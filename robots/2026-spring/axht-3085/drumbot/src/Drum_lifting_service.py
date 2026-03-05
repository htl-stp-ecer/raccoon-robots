from libstp import slow_servo, parallel, motor_power, Step, seq, motor_off
from libstp.step import servo
from pydantic.json_schema import DefsRef
from raccoon.commands.calibrate import motors_command

from src.hardware import defs
from src.hardware.defs import Defs


class DrumLiftingService(Step):

    def __init__(self, degrees, speed):
        super().__init__()
        self.degrees = degrees
        self.speed = speed          #in degrees per second

    async def _execute_step(self, robot: "GenericRobot") -> None:
        deltaAngle = self.degrees - servo.get_position(Defs.lift_drums_servo)
        if deltaAngle < 0:
            motorspeed = 50
        else :
            motorspeed = -50

        motor_power(Defs.servo_help_motor, motorspeed)
        slow_servo(Defs.lift_drums_servo ,self.degrees,self.speed)
        motor_off(Defs.servo_help_motor)




def DrumLiftingServiceUP():
    return seq([
        DrumLiftingService(degrees=170, speed=10),
        motor_off(Defs.servo_help_motor)
    ])

def DrumLiftingServiceMiddle() -> None:
    DrumLiftingService(degrees=70, speed=10).move()


def DrumLiftingServiceDown() -> None:
    DrumLiftingService(degrees=20, speed=10).move()


