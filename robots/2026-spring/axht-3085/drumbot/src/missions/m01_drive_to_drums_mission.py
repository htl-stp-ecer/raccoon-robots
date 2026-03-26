from libstp import *

from src.steps.drum_collector.move_by_offset_step import MoveDrumMotorByOffsetStep
from src.steps.drum_lifting_step import drum_lifting_up
from src.steps.servo_steps import swap_pom_remover_servo, driving_position_pom_remover_servo


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
             parallel(
                 drive_forward(65,1),
                 seq([swap_pom_remover_servo(), wait_for_seconds(3.2), driving_position_pom_remover_servo()])),
        ])