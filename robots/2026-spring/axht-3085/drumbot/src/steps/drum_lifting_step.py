from raccoon import *
from raccoon.step.servo.preset import _PresetPosition

from src.hardware.defs import Defs


def _lift_drum_servo(
        target_position: _PresetPosition,
        servo_speed: int,
        base_motor_speed=60,
        servo_ref=Defs.lift_drums_servo.device,
        motor_ref=Defs.servo_help_motor,
        slow_mode=True,
) -> Defer:
    def _build(_):
        delta_angle = target_position.value - servo_ref.get_position()
        move_with_slow_servo = slow_mode

        sequence = []
        info(f"Current servo position: {servo_ref.get_position()} degrees, target: {target_position} degrees, delta: {delta_angle} degrees")
        if delta_angle > 0:
            sequence.append(set_motor_power(motor_ref, -base_motor_speed))
            move_with_slow_servo = False
        sequence.extend([
            target_position(),
            #servo(servo_ref, degrees) if move_with_slow_servo else servo(servo_ref, degrees),
            motor_passive_brake(motor_ref),
        ])

        return seq(sequence)

    return defer(_build)


def drum_lifting_up(slow_mode=True) -> Defer:
    return _lift_drum_servo(
        target_position=Defs.lift_drums_servo.up,
        servo_speed=25,
        slow_mode=slow_mode,
    )

def drum_align_on_back(slow_mode=True) -> Defer:
    return _lift_drum_servo(
        target_position=Defs.lift_drums_servo.align_on_back,
        servo_speed=999,
        slow_mode=slow_mode,
    )

def drum_eject_position(slow_mode=True) -> Defer:
    return _lift_drum_servo(
        target_position=Defs.lift_drums_servo.eject_position,
        servo_speed=120,
        slow_mode=slow_mode,
    )

def drum_seek(slow_mode=True) -> Defer:
    return _lift_drum_servo(
        target_position=Defs.lift_drums_servo.seek_position,
        servo_speed=25,
        slow_mode=slow_mode,
    )


def drum_lifting_down(slow_mode=True) -> Defer:
    return _lift_drum_servo(
        target_position=Defs.lift_drums_servo.down,
        servo_speed=999,
        slow_mode=slow_mode,
    )


def drum_lifting_remove_D(slow_mode=True) -> Defer:
    return _lift_drum_servo(
        target_position=Defs.lift_drums_servo.remove_D,
        servo_speed=999,
        slow_mode=slow_mode,
    )

def drum_lifting_remove_M(slow_mode=True) -> Defer:
    return _lift_drum_servo(
        target_position=Defs.lift_drums_servo.remove_M,
        servo_speed=999,
        slow_mode=slow_mode,
    )

def drum_lifting_up_over_limit():
    return seq([
        drum_lifting_up(),

        #motor pushes the rum further back
        fully_disable_servos(),
        set_motor_power(Defs.servo_help_motor, -100),
        wait_for_seconds(0.5),
        motor_passive_brake(Defs.drum_motor),
    ])
