from libstp import *

from src.steps.drive_to_pipe import drive_to_first_pipe
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_up, shake_drums, drum_lifting_remove_D, drum_lifting_remove_M
from src.steps.range_finder import turn_to_peak
from src.hardware.defs import Defs


class M03DriveToPipe(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #drum_retreat(),

            #drive to first black line and turn
            drum_lifting_up(),
            drive_backward().until(
                on_black(Defs.front_right_ir_sensor)
            ),
            turn_to_heading_right(180),

            drive_to_first_pipe(),
            turn_to_peak(turn_speed=0.4, profile="first_pipe"),
            #turn_left(19.5, 1),

            wall_align_forward(speed=0.3, accel_threshold=0.3, settle_duration=0.4, max_duration=3, grace_period=0.4),
            parallel(
                drive_backward(3.2, 1),
                shake_drums()
            ),

        ])
