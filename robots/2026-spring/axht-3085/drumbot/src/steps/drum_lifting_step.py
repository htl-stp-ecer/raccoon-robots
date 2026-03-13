from libstp import *

from src.hardware.defs import Defs


def _lift_drum_servo(
        degrees,
        servo_speed,
        base_motor_speed=60,
        servo_ref=Defs.lift_drums_servo,
        motor_ref=Defs.servo_help_motor,
        slow_mode=True
) -> Defer:
    def _build(_):
        delta_angle = degrees - servo_ref.get_position()
        move_with_slow_servo = slow_mode

        sequence = []
        info(f"Current servo position: {servo_ref.get_position()} degrees, target: {degrees} degrees, delta: {delta_angle} degrees")
        if delta_angle > 0:
            sequence.append(set_motor_power(motor_ref, -base_motor_speed))
            move_with_slow_servo = False
        sequence.extend([
            servo(servo_ref, degrees) if move_with_slow_servo else servo(servo_ref, degrees),
            motor_passive_brake(motor_ref),
        ])

        return seq(sequence)

    return defer(_build)


def drum_lifting_up(slow_mode=True) -> Defer:
    return _lift_drum_servo(degrees=170, servo_speed=25, slow_mode=slow_mode)

def dispense_drums(slow_mode=True) -> Defer:
    return _lift_drum_servo(degrees=150, servo_speed=25, slow_mode=slow_mode)

def drum_lifting_middle(slow_mode=True) -> Defer:
    return _lift_drum_servo(degrees=120, servo_speed=25, slow_mode=slow_mode)


def drum_lifting_down(slow_mode=True) -> Defer:
    return _lift_drum_servo(degrees=5, servo_speed=25, slow_mode=slow_mode)
