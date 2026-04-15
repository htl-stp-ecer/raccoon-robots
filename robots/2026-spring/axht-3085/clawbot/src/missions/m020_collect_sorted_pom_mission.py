from raccoon import *

from src.hardware.defs import Defs


class M020CollectSortedPomMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("default"),

            # disable the claw and move shild down and open
            background(
                step=seq([
                    fully_disable_servos(),
                    wait_for_seconds(0.05),
                    parallel(
                        Defs.shild.normal_drive(),
                        Defs.shild_graber.wide_open(),
                    ),
                ]),
            ),

            # turn straight
            turn_to_heading_left(90, 1.0),

            # drive to orange pom
            strafe_right().until(
                on_black(Defs.rear.right),
            ),
            strafe_left().until(
                on_white(Defs.rear.right) +
                after_cm(3)
            ),

            #collect first pom
            drive_backward().until(
                on_black(Defs.rear.right)
            ),

            # open shild
            parallel(
                Defs.shild.down(),
                Defs.shild_graber.closed(70),
            ),

            # put the shild temporarly up
            background(
                Defs.shild.up(),
            ),

            # drive over line and turn to grab the second and third oragne pom
            turn_to_heading_right(0),
            strafe_left().until(
                on_white(Defs.rear.right) +
                after_cm(3)
            ),
            drive_forward().until(
                on_black(Defs.rear.right)
            ),
            turn_to_heading_right(90),

            #put the shild down
            background(
                step=seq([
                        Defs.shild.normal_drive(),
                        Defs.shild_graber.wide_open(100),
                ]),
            ),
            strafe_left().until(
                over_line(Defs.rear.right) +
                after_cm(2)
            ),

            drive_backward(cm=13),

            turn_right(18, 1.0),
            drive_backward(10, 1.0),
            turn_to_heading_right(90, 1.0),

            wall_align_backward(1.0, 0.6, 0.0, 1.5),
            # mark heading for collecting the poms (0 heading is now in the direction of the black line)
            mark_heading_reference(),

            drive_angle(angle_deg=110).until(on_black(Defs.rear.right, threshold=0.3)),

            Defs.shild.down(),
            Defs.shild_graber.closed(70),
            # grab the pom set
            Defs.shild.save_up(),
        ])
