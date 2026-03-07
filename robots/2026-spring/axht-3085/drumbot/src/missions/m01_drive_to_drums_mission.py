from libstp import *

from src.steps.drum_lifting_step import drum_lifting_up


class M01DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_backward(4),
            drum_lifting_up(),
            turn_right(90),
            drive_forward(85),
        ])