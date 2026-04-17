from raccoon import *

from src.hardware.defs import Defs
from src.steps.cone_container_steps import down_cone_container


class M000SetupMission(SetupMission):
    def sequence(self) -> Sequential:
        return seq([
            fully_disable_servos(),
            wait_for_button("Move Servos"),
            motor_off(Defs.cone_container_motor),
            Defs.claw_servo.closed(),
            Defs.cone_arm_servo.container_pos(),

            calibrate(distance_cm=50,
                      calibration_sets=["default", "upper"],
            ),
            switch_calibration_set("default"),

            Defs.cone_arm_servo.handl_hight(),

            Defs.cone_arm_servo.container_pos()
        ])
