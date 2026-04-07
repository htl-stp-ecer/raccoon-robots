from libstp import *

from src.hardware.defs import Defs


class M090RetrunBasketsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # return sorted basket
            parallel(
                timeout(
                    strafe_arc_left(
                        radius_cm=45,
                        degrees=70,
                        speed=1.0
                    ),
                    seconds=6
                ),

                seq([
                    wait_until_degrees(45),
                    Defs.shild._45deg(),
                ])
            ),
            turn_to_heading_left(0, speed=0.3),  # turn straight

            #push basket further in
            strafe_left(cm=17),
            Defs.shild.down(),
            strafe_right(cm=17),
            strafe_left(cm=5),

            #put the shild up so we dont hit the wall
            background(
                Defs.shild.save_up(),
            ),


            #position mached basket to return
            drive_backward().until(
                over_line(Defs.rear.right) +
                after_cm(17),
            ),

            #return mached basket
            turn_right(20),
            Defs.pom_arm.high_above_basket(),
            turn_left(50),

            Defs.pom_arm.down(),
            turn_to_heading_right(35), #push basket in



        ])