"""Auto-generated type stub — Raccoon Toolchain (Tobias Madlberger / RaccoonOS Team)"""

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
    save_up: _PresetPosition
    _45deg: _PresetPosition
    down: _PresetPosition
    normal_drive: _PresetPosition
    above_pasked: _PresetPosition
    grab_pasked: _PresetPosition
    high_up: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _PomArmPreset(ServoPreset):
    down: _PresetPosition
    above_pom: _PresetPosition
    high_above_basket: _PresetPosition
    above_basket: _PresetPosition
    in_basket: _PresetPosition
    up: _PresetPosition
    drop_poms_pos: _PresetPosition
    start: _PresetPosition
    high_up: _PresetPosition
    _90deg: _PresetPosition

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
    m05_collect_poms: _PresetPosition
    m05_slightly_open: _PresetPosition
    shake_pos_a: _PresetPosition
    shake_pos_b: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class Defs:
    imu: Imu
    button: DigitalSensor
    distance_sensor: AnalogSensor
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
