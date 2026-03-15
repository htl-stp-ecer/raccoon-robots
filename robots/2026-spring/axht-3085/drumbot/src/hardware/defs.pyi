"""Auto-generated type stub for defs.py — DO NOT EDIT."""

from libstp import AnalogSensor
from libstp import DigitalSensor
from libstp import ETSensor
from libstp import IMU as Imu
from libstp import IRSensor
from libstp import Motor
from libstp import Servo
from libstp.step.servo.preset import ServoPreset
from typing import List


class Defs:
    imu: Imu
    button: DigitalSensor
    front_left_motor: Motor
    front_right_motor: Motor
    front_left_ir_sensor: IRSensor
    front_right_ir_sensor: IRSensor
    drum_pusher_servo: Servo
    pom_remover_servo: Servo
    drum_motor: Motor
    servo_help_motor: Motor
    lift_drums_servo: Servo
    drum_light_sensor: IRSensor
    wait_for_light_sensor: AnalogSensor
    et_range_finder: ETSensor
    analog_sensors: List[AnalogSensor]
