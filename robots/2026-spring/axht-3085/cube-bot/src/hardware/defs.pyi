"""Auto-generated type stub for defs.py — DO NOT EDIT."""

from libstp import AnalogSensor
from libstp import DigitalSensor
from libstp import IMU as Imu
from libstp import IRSensor
from libstp import Motor
from libstp.step.motion.sensor_group import SensorGroup
from libstp.step.servo.preset import ServoPreset, _PresetPosition
from typing import List


class _ShildPreset(ServoPreset):
    up: _PresetPosition
    _45deg: _PresetPosition
    down: _PresetPosition
    normal_drive: _PresetPosition
    above_pasked: _PresetPosition
    grab_pasked: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _PomArmPreset(ServoPreset):
    down: _PresetPosition
    above_pom: _PresetPosition
    above_basket: _PresetPosition
    up: _PresetPosition
    start: _PresetPosition
    high_up: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _ShildGraberPreset(ServoPreset):
    open: _PresetPosition
    wide_open: _PresetPosition
    closed: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _PomGrabPreset(ServoPreset):
    closed: _PresetPosition
    start: _PresetPosition
    pom_width: _PresetPosition
    slightly_open: _PresetPosition
    open: _PresetPosition
    wide_open: _PresetPosition
    magic_val_for_m06: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class Defs:
    imu: Imu
    button: DigitalSensor
    rear_right_light_sensor: IRSensor
    wait_for_light_sensor: AnalogSensor
    front_right_light_sensor: IRSensor
    front_left_light_sensor: IRSensor
    front: SensorGroup
    rear: SensorGroup
    front_left_motor: Motor
    front_right_motor: Motor
    rear_left_motor: Motor
    rear_right_motor: Motor
    shild: _ShildPreset
    pom_arm: _PomArmPreset
    shild_graber: _ShildGraberPreset
    pom_grab: _PomGrabPreset
    analog_sensors: List[AnalogSensor]
