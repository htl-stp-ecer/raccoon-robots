from libstp import Mission, Sequential, seq, turn_right, strafe_right_until_black, drive_backward

from src.hardware.defs import Defs


class GrabSecondPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            turn_right(90, 1.0),
            strafe_right_until_black(Defs.front_right_light_sensor, 1.0),
            drive_backward(10, 1.0)
        ])
