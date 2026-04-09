"""Auto-generated type stub — Raccoon Toolchain (Tobias Madlberger / RaccoonOS Team)"""

from libstp import AnalogSensor
from libstp import DigitalSensor
from libstp import ETSensor
from libstp import IMU as Imu
from libstp import IRSensor
from libstp import Motor
from libstp import Servo
from libstp.step.servo.preset import ServoPreset, _PresetPosition
from typing import List


class _PomRemoverServoPreset(ServoPreset):
    start: _PresetPosition
    push_first_orange_pom_away: _PresetPosition
    push_blue_pom_away: _PresetPosition
    standby: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class Defs:
    imu: Imu
    button: DigitalSensor
    front_left_ir_sensor: IRSensor
    front_right_ir_sensor: IRSensor
    drum_light_sensor: IRSensor
    wait_for_light_sensor: AnalogSensor
    et_range_finder: ETSensor
    IR_Distanz_to_pipe_sensor: ETSensor
    front_left_motor: Motor
    front_right_motor: Motor
    drum_motor: Motor
    servo_help_motor: Motor
    drum_pusher_servo: Servo
    pom_remover_servo: _PomRemoverServoPreset
    lift_drums_servo: Servo
    analog_sensors: List[AnalogSensor]
