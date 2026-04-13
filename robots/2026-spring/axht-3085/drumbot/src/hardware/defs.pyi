"""Auto-generated type stub — Raccoon Toolchain (Tobias Madlberger / RaccoonOS Team)"""

from raccoon import AnalogSensor
from raccoon import DigitalSensor
from raccoon import ETSensor
from raccoon import IMU as Imu
from raccoon import IRSensor
from raccoon import Motor
from raccoon.step.servo.preset import ServoPreset, _PresetPosition
from typing import List


class _DrumPusherServoPreset(ServoPreset):
    close: _PresetPosition
    open: _PresetPosition
    block_angle: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _PomRemoverServoPreset(ServoPreset):
    start: _PresetPosition
    right: _PresetPosition
    r_cube: _PresetPosition
    left: _PresetPosition
    center: _PresetPosition
    orange_pom_removel: _PresetPosition

    @property
    def device(self) -> "Servo": ...


class _LiftDrumsServoPreset(ServoPreset):
    up: _PresetPosition
    align_on_back: _PresetPosition
    eject_position: _PresetPosition
    seek_position: _PresetPosition
    down: _PresetPosition
    remove_D: _PresetPosition
    remove_M: _PresetPosition

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
    drum_pusher_servo: _DrumPusherServoPreset
    pom_remover_servo: _PomRemoverServoPreset
    lift_drums_servo: _LiftDrumsServoPreset
    analog_sensors: List[AnalogSensor]
    wait_for_light_mode: str
