from libstp import *

from src.hardware.defs import Defs


class DriveDownAccesRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # strafe_left_until_black(Defs.front_left_light_sensor, 0.5),
            strafe_left_lineup_on_black(Defs.front_left_light_sensor, Defs.rear_left_light_sensor, 0.4),
            strafe_left(5, 1.0),
            wait(1),
            drive_forward(115.0, 0.5)
        ])
