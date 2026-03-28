"""Auto-generated type stub — Raccoon Toolchain (Tobias Madlberger / RaccoonOS Team)"""


from libstp import IMU as Imu
from libstp import AnalogSensor, DigitalSensor, ETSensor, IRSensor, Motor, Servo

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
    analog_sensors: list[AnalogSensor]
