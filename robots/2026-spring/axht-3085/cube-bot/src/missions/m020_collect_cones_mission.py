from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import drop_cone_into_holder


def line_follow(speed: float = 1):
    return strafe_follow_line_single(
        Defs.front.left,
        speed=speed,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.2,
        kd=0.0,
    )

class M020CollectConesMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            strafe_left().until(   # TODO: use a sideways line follow
                over_line(Defs.rear.left)
                # + over_line(Defs.front_right_light_sensor)
                + after_cm(23),
            ),

            # position arm over first cone grab position to avoid
            # pushing pom, then lower it
            background(
                seq([
                    parallel(
                        arm.move_angles(-12, 10, -10),
                        Defs.arm_claw.p90deg(),
                    ),
                    wait_for_seconds(2.5),
                    arm.move_angles(-12, -10, 20),
                ]),
            ),

            # drive to line
            drive_angle(angle_deg=-75).until(
                over_line(Defs.rear_left_light_sensor)
                + over_line(Defs.front_left_light_sensor)
            ),
            turn_to_heading_right(0),

            # follow the line and grab the cones in parallel
            parallel(
                seq([
                    line_follow().until(
                        over_line(Defs.front.right)
                    ),
                    line_follow(speed=0.7).until(
                        over_line(Defs.front.right)
                    ),
                    line_follow().until(
                        after_cm(5)   # make sure we are over the line (for strafing)
                    )
                ]),
                seq([
                    # wait until we reach the first T --> grab --> then drop into holder
                    wait_for(on_black(Defs.front.right)),
                    Defs.arm_claw.closed(),   # grab cone
                    drop_cone_into_holder(base_angle=17),

                    # position arm so we can grab the second cone
                    parallel(
                        arm.move_angles(-12, -10, 20),
                        Defs.arm_claw.p90deg(),
                    ),

                    # wait until we reach the second T --> grab --> then drop into holder
                    wait_for(on_black(Defs.front.right)),
                    background(
                        step=seq([
                            Defs.arm_claw.closed(),   # grab cone
                            drop_cone_into_holder(base_angle=35),
                        ]),
                        name="drop_cone",
                    ),
                ]),
            ),
        ])
