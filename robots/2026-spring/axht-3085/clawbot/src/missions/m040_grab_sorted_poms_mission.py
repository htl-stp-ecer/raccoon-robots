from libstp import *

from src.hardware.defs import Defs
from src.steps.line_cross_detecting_turn import LineCrossDetectingTurn


class M040GrabSortedPomsMission(Mission):
    def sequence(self) -> Sequential:
        line_turn = LineCrossDetectingTurn(
            target_heading=90,
            tracking_start_deg=45,
            sensor=Defs.rear.right,
        )

        return seq([
            #push a blue pom to collect it later
            background(
                seq([
                    wait_for_seconds(0.4),
                    Defs.pom_arm.start(100),
                ]),
                name="put claw up"
            ),

            line_turn,
            wait_for_background("put claw up"),

            parallel(
                seq([
                    # If we crossed the line during the turn, we're on the right
                    # side — strafe right to re-find it. Otherwise strafe left.
                    defer(lambda robot: (
                        strafe_right().until(on_black(Defs.rear.right))
                        if line_turn.crossed_line
                        else strafe_left().until(on_black(Defs.rear.right))
                    )),
                    strafe_left(cm=13), #magic hardcoded value :)
                ]),

                #prepare the shield to grab the sorted poms
                Defs.shild.normal_drive(),
                Defs.shild_graber.wide_open(),
            ),
            turn_to_heading_right(90, 1.0),

            drive_backward(30, 1.0),

            wall_align_backward(1.0, 0.6, 0.0, 3.0),
            # mark heading for collecting the poms (0 heading is now in the direction of the black line)
            mark_heading_reference(),

            drive_angle(angle_deg=110).until(on_black(Defs.rear.right, threshold=0.3)),

            Defs.shild.down(),
            Defs.shild_graber.closed(70),
            #grab the pom set
            Defs.shild.save_up(),
        ])
