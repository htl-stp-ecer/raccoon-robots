from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_down, shake_drums, dispense_drums
from src.steps.servo_steps import open_drum_pusher, close_drum_pusher


@dsl
def reject_drums(offset_velocity: int = -1000, offset_time: float = 0.3,) -> Sequential:
    sequence = []


    drums = 1


    def _block():
        return seq([
            drum_retreat(),
            # relative soon
            set_motor_velocity(Defs.drum_motor, offset_velocity),
            wait_for_seconds(offset_time),
            motor_passive_brake(Defs.drum_motor),
        ])

    for i in range(drums):
        sequence.append(_block())

    return seq(sequence)


class M04RejectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            reject_drums(),
            reject_drums(),
           # shake_drums(),
            #dispense_drums(),
            reject_drums(),
            reject_drums(),
            reject_drums(),
        ])
