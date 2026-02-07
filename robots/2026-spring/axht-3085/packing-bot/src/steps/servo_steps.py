from libstp import *
from libstp.step.servo import slow_servo

from src.hardware.defs import *

# --- pom arm
@dsl
def servo_pom_arm_down():
    return slow_servo(Defs.pom_arm, 0, 20)

@dsl
def servo_pom_arm_up():
    return slow_servo(Defs.pom_arm, 70, 20)

@dsl
def servo_pom_arm_start():
    return servo(Defs.pom_arm, 120)

# --- pom grab ---
@dsl
def servo_pom_grab_close():
    return slow_servo(Defs.pom_grab, 30, 20)

@dsl
def servo_pom_grab_open():
    return slow_servo(Defs.pom_grab, 100, 20)
