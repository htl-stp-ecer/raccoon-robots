from raccoon import *

from src.hardware.defs import Defs

def line_follow():
    return strafe_follow_line_single(
        Defs.front_left_light_sensor,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.2,
        kd=0.1,
    )

class M010DriveDownRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("upper"),
            mark_heading_reference(),

            #drive to black line
            turn_left(25),
            drive_backward().until(
                over_line(Defs.rear_left_light_sensor)
                + on_black(Defs.rear_left_light_sensor)
            ),
            turn_to_heading_right(0),

            #make sure we are centered on black line
            line_follow().until(after_cm(30)),

            #drive the rest down the line
            drive_backward().until(
                after_cm(80)
                + on_black(Defs.front_right_light_sensor)
                + after_cm(2)
            ),
            switch_calibration_set("default"),
        ])