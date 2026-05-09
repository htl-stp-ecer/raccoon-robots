from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm

def line_follow():
    return strafe_follow_line_single(
        Defs.front_left_light_sensor,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.1,
        kd=0.0,
    )

class M020CollectConesMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            strafe_left().until( #TODO: use a sidways line follow
                over_line(Defs.rear_left_light_sensor)
                #+ over_line(Defs.front_right_light_sensor)
                +after_cm(23),
            ),
            #positon arm to grab first cone
            background(
                step=arm.move_to(35, -5, 5).forearm(angle=0, precision=1),
            ),
            background(
                step=Defs.arm_claw.p90deg(),
            ),
            #drive to line
            drive_angle(angle_deg=-50).until(
                over_line(Defs.rear_left_light_sensor)
                + over_line(Defs.front_left_light_sensor)
            ),

            #follow the line and grab the cones in parralel
            parallel(
                line_follow().until(
                    over_line(Defs.front_right_light_sensor)
                    + over_line(Defs.front_right_light_sensor)
                ),
                seq([
                    #wati until we reach the first T --> grab --> then drop into holder
                    wait_for(on_black(Defs.front_right_light_sensor)),
                    Defs.arm_claw.closed(),
                    arm.move_angles(-11, 92, 85),
                    Defs.arm_claw.p45deg(),
                    wait_for_seconds(1), #wait so the cone drops for 100%

                    #position arm so we can grab the second conde
                    parallel(
                        arm.move_to(35, -5, 5).forearm(angle=0, precision=0.8),
                        Defs.arm_claw.p90deg(),
                    ),

                    #wati until we reach the second T --> grab --> then drop into holder
                    wait_for(on_black(Defs.front_right_light_sensor)),
                    Defs.arm_claw.closed(),
                    arm.move_angles(-40, 100, 75),
                    Defs.arm_claw.p45deg(),
                ]),

            ),
        ])