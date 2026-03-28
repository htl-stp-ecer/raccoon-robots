from libstp import *

from src.steps.drum_lifting_step import drum_lifting_up
from src.steps.servo_steps import driving_position_pom_remover_servo, swap_pom_remover_servo


class M01DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                 drum_lifting_up(),
                 seq([
                     wait_for_seconds(0.4),
                     turn_right(90),
                 ]),
             ),
             parallel(
                 drive_forward(65,1),
                 seq([
                     swap_pom_remover_servo(),
                     wait_for_seconds(1.1),
                     driving_position_pom_remover_servo()
                 ]),
             ),
        ])
