from libstp import *
from libstp.step.servo import slow_servo

from src.hardware.defs import *

# --- pom arm
@dsl
def servo_pom_arm_down(speed = 100):
    return slow_servo(Defs.pom_arm, 0, speed)

@dsl
def servo_pom_arm_up(speed = 100):
    return slow_servo(Defs.pom_arm, 60, speed)

@dsl
def servo_pom_arm_above_pom(speed = 100):
    return slow_servo(Defs.pom_arm, 30, speed)

@dsl
def servo_pom_arm_start():
    return slow_servo(Defs.pom_arm, 150, 200)

# --- pom grab ---
@dsl
def servo_pom_grab_start(speed = 80): #closes the claw but doesn't  not as tight as the close cmd
    return slow_servo(Defs.pom_grab, 30, speed)

@dsl
def servo_pom_grab_close(speed = 80):
    return slow_servo(Defs.pom_grab, 0, speed)

@dsl
def servo_pom_grab_pom_width(speed = 120): #open die claw only a bit wider as a pom diameter
    return slow_servo(Defs.pom_grab, 45, speed)

@dsl
def servo_pom_grab_slightly_open(speed = 120):
    return slow_servo(Defs.pom_grab, 70, speed)

@dsl
def servo_pom_grab_open(speed = 120):
    return slow_servo(Defs.pom_grab, 100, speed)

@dsl
def servo_pom_grab_wide_open(speed = 120):
    return slow_servo(Defs.pom_grab, 130, speed)
