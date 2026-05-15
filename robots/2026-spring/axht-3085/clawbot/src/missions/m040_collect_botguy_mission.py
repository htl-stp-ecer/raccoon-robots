from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm

def backward_line_follow():
    return strafe_follow_line_single(
        Defs.front.left,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.2,
        kd=0.0,
    )

class M040CollectBotguyMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from black line
            drive_backward().until(
                on_white(Defs.front.left)
            ),

            # follow line to botguy pickup
            backward_line_follow().until(
                over_line(Defs.rear.left)
            ),

            # wait for completion of tray return and turn after
            # wait_for_background("return_tray"),
            # arm.move_angles(-90, 50, -80),
            # turn_to_heading_left(90),
        ])