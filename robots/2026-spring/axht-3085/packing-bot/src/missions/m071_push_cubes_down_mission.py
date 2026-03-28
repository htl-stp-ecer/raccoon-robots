from libstp import *

from src.hardware.defs import Defs


class M071PushCubesDownMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # position to throw cubes down
            strafe_left().until(
                on_black(Defs.front.right) >
                on_white(Defs.front.right)
            ),
            # throw cubes down
            parallel(
                turn_to_heading_right(degrees=45),
                Defs.pom_arm.up(100),
            ),
            turn_left().until(after_seconds(0.7)),
            parallel(
                Defs.pom_arm.start(),
                turn_to_heading_left(0),
            ),

            # we now sand someware and baskets are to the right of us :)
        ])