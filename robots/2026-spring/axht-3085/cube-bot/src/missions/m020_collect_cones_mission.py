from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import drop_cone_into_holder


def line_follow():
    return strafe_follow_line_single(
        Defs.front_left_light_sensor,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.2,
        kd=0.0,
    )



class M020CollectConesMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            strafe_left().until(  # TODO: use a sidways line follow
                over_line(Defs.rear_left_light_sensor)
                # + over_line(Defs.front_right_light_sensor)
                + after_cm(23),
            ),
            # positon arm to grab first cone
            background(
                step=parallel(
                    arm.move_angles(-12, -10, 20),
                    Defs.arm_claw.p90deg(),
                )
            ),
            # drive to line
            drive_angle(angle_deg=-75).until(
                over_line(Defs.rear_left_light_sensor)
                + over_line(Defs.front_left_light_sensor)
            ),

            turn_to_heading_right(0),
            # follow the line and grab the cones in parralel
            parallel(
                line_follow().until(
                    over_line(Defs.front.right)
                    + over_line(Defs.front.right)
                    + after_cm(5) #make sure we are over the line (for strafing)
                ),
                seq([
                    # wait until we reach the first T --> grab --> then drop into holder
                    wait_for(on_black(Defs.front.right)),
                    Defs.arm_claw.closed(), #grab cone
                    drop_cone_into_holder(base_angle=-10),

                    # position arm so we can grab the second conde
                    parallel(
                        arm.move_angles(-12, -10, 20),
                        Defs.arm_claw.p90deg(),
                    ),

                    # wait until we reach the second T --> grab --> then drop into holder
                    wait_for(on_black(Defs.front.right)),
                    background(
                        step=seq([
                            Defs.arm_claw.closed(),#grab cone
                            drop_cone_into_holder(base_angle=25),
                        ]),
                        name="drop_cone",
                    ),
                ]),

            ),
        ])
