from libstp import *

from src.hardware.defs import Defs

def strafte_if_on_black(sensor):
    def _build(robot):
        if sensor.isOnBlack():
            return seq([
                strafe_left().until(
                    on_white(sensor) +
                    after_cm(5)
                )
            ])
        else:
            return seq([])
    return defer(_build) #defer = evaluate _build funciton at runtime and not compiletime

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
                    # put the shild up so we dont hit the wall
                    Defs.shild.high_up(),
                ])
            ),

            turn_to_heading_left(0, speed=0.3),  # turn straight

            strafte_if_on_black(Defs.rear.right),

            #position mached basket to return
            drive_backward().until(
                after_cm(30) +
                on_black(Defs.front.right)
            ),
            drive_forward(cm=7),

            #return mached basket
            turn_right(20),
            parallel(
                Defs.pom_arm.high_above_basket(),
                Defs.pom_grab.open(),
            ),
            parallel(
                turn_left(50),
                Defs.pom_grab.closed(),
            ),

            Defs.pom_arm.down(),
            turn_to_heading_right(30), #push basket in



        ])