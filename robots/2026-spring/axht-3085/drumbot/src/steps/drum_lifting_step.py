from libstp import *

from src.hardware.defs import Defs


def _lift_drum_servo(
        degrees,
        servo_speed,
        base_motor_speed=50,
        servo_ref=Defs.lift_drums_servo,
        motor_ref=Defs.servo_help_motor):
    def _build(_):
        delta_angle = degrees - servo_ref.get_position()
        motor_speed = base_motor_speed if delta_angle < 0 else -base_motor_speed

        return seq([
            motor_power(motor_ref, motor_speed),
            slow_servo(servo_ref, degrees, servo_speed),
            motor_off(motor_ref),
        ])

    return defer(_build)


def drum_lifting_service_up():
    return _lift_drum_servo(degrees=70, servo_speed=10)


def drum_lifting_service_middle() -> None:
    return _lift_drum_servo(degrees=70, servo_speed=10)


def drum_lifting_service_down() -> None:
    return _lift_drum_servo(degrees=20, servo_speed=10)
