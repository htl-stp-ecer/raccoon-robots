from libstp import *

from src.steps.drum_collector.move_by_offset_step import MoveDrumMotorByOffsetStep
from src.steps.drum_lifting_step import drum_lifting_up


class M01DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                 drum_lifting_up(),
                 seq([
                     wait_for_seconds(0.4),
                     turn_right(90),
                 ])
             ),
             drive_forward(66,1),
        ])