"""Auto-generated type stub — Raccoon Toolchain (Tobias Madlberger / RaccoonOS Team)"""

from raccoon import AnalogSensor
from raccoon import DigitalSensor
from raccoon import IMU as Imu
from raccoon import IRSensor
from raccoon import Motor
from raccoon.step.motion.sensor_group import SensorGroup
from raccoon.step.servo.preset import ServoPreset, _PresetPosition
from typing import List


class _ArmBasePreset(ServoPreset):
    _0deg: _PresetPosition
    p90deg: _PresetPosition
    max_left: _PresetPosition
    m90deg: _PresetPosition
    max_right: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _ArmSholderPreset(ServoPreset):
    max_down: _PresetPosition
    _0deg: _PresetPosition
    p90deg: _PresetPosition
    max_up: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _ArmElbowPreset(ServoPreset):
    _0deg: _PresetPosition
    p90deg: _PresetPosition
    max_max: _PresetPosition
    m90deg: _PresetPosition
    max_minus: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _ArmClawPreset(ServoPreset):
    closed: _PresetPosition
    soft_close: _PresetPosition
    p45deg: _PresetPosition
    p90deg: _PresetPosition
    p135deg: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class Defs:
    imu: Imu
    button: DigitalSensor
    rear_left_light_sensor: IRSensor
    wait_for_light_sensor: AnalogSensor
    front_right_light_sensor: IRSensor
    front_left_light_sensor: IRSensor
    front: SensorGroup
    rear: SensorGroup
    front_left_motor: Motor
    front_right_motor: Motor
    rear_left_motor: Motor
    rear_right_motor: Motor
    arm_base: _ArmBasePreset
    arm_sholder: _ArmSholderPreset
    arm_elbow: _ArmElbowPreset
    arm_claw: _ArmClawPreset
    analog_sensors: List[AnalogSensor]
    wait_for_light_mode: str
