from libstp import *

from src.steps.drum_lifting_step import drum_lifting_up


class M01DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_backward(2),
            parallel([
                drum_lifting_up(),
                seq([
                    wait(0.5),
                    drive_forward(2),
                ]),
            ]),
            turn_right(90),
        ])