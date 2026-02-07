from libstp import *
from libstp.step.servo import slow_servo

from src.hardware.defs import *

# --- pom arm
@dsl
def servo_pom_arm_down():
    return slow_servo(Defs.pom_arm, 0, 1)

@dsl
def servo_pom_arm_up():
    return slow_servo(Defs.pom_arm, 70, 1)

@dsl
def servo_pom_arm_start():
    return slow_servo(Defs.pom_arm, 120, 5)

# --- pom grab ---
@dsl
def servo_pom_grab_close():
    return slow_servo(Defs.pom_grab, 30, 1.5)

@dsl
def servo_pom_grab_open():
    return slow_servo(Defs.pom_grab, 100, 1.5)
