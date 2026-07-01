import math
import time

from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_eject_position


def _heading_stuck(grace_seconds: float = 0.3, threshold_deg: float = 5.0, stuck_duration: float = 0.2):
    """Stop when heading hasn't changed beyond threshold for stuck_duration, after an initial grace period."""
    start_time = None
    last_heading = None
    last_change_time = None

    def _check(robot):
        nonlocal start_time, last_heading, last_change_time
        now = time.monotonic()
        if start_time is None:
            start_time = now
            last_heading = math.degrees(Defs.imu.get_heading())
            last_change_time = now
            return False
        if now - start_time < grace_seconds:
            last_heading = math.degrees(Defs.imu.get_heading())
            last_change_time = now
            return False
        heading = math.degrees(Defs.imu.get_heading())
        if abs(heading - last_heading) > threshold_deg:
            last_heading = heading
            last_change_time = now
        return now - last_change_time >= stuck_duration

    return custom(_check)


def _drive_to_drum_button():
    """Drive forward until drum button is pressed; retry if already pressed."""

    def _build(_):
        if Defs.drum_found_button.read():
            return seq([
                drive_backward(speed=0.2).until(on_digital(Defs.drum_found_button, pressed=False)),
                drive_backward(2, speed=0.2),
                drive_forward(speed=0.2).until(on_digital(Defs.drum_found_button) | after_cm(8)),
            ])
        else:
            return seq([
                drive_forward(speed=0.2).until(on_digital(Defs.drum_found_button) | after_cm(15)),
            ])

    return defer(_build)


@dsl
def lineup_drum_with_pipe():
    return seq([
        # drum_servo_step,
        Defs.lift_drums_servo.seek_position(),
        wait_for_seconds(0.5),
        turn_right().until(
            _heading_stuck(stuck_duration=0.5, threshold_deg=4)
            | on_digital(Defs.drum_found_button)
            | after_degrees(60)
        ),
        wait_for_seconds(0.5),
        _drive_to_drum_button(),
        parallel(
            drive_backward(6, speed=0.2),

            # Park one pocket before the group BEFORE lifting — this rotation drops
            # nothing because the eject mechanism is still disengaged.
            Defs.lift_drums_servo.eject_position(70),
        ),
        wait_for_seconds(0.5),
    ])
