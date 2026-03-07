from libstp import *

from src.steps.drum_lifting_step import drum_lifting_up


class M01DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                drum_lifting_up(),
                seq([
                    wait(0.4),
                    turn_right(90),
                ])
            ),
            drive_forward(77),
        ])