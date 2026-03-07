from libstp import *
from libstp.step.servo import slow_servo

from src.hardware.defs import *

# --- pom arm
@dsl
def servo_pom_arm_down(speed: int = 100):
    return slow_servo(Defs.pom_arm, 0, speed)

@dsl
def servo_pom_arm_up(speed: int = 100):
    return slow_servo(Defs.pom_arm, 90, speed)

@dsl
def servo_pom_arm_above_pom(speed: int = 100):
    return slow_servo(Defs.pom_arm, 30, speed)

@dsl
def servo_pom_arm_high_up(speed: int = 400):
    return slow_servo(Defs.pom_arm, 140, speed)

@dsl
def servo_pom_arm_start(speed: int = 400):
    return slow_servo(Defs.pom_arm, 140, speed)

# --- pom grab ---
@dsl
def servo_pom_grab_start(speed: int = 80): #closes the claw but doesn't  not as tight as the close cmd
    return slow_servo(Defs.pom_grab, 30, speed)

@dsl
def servo_pom_grab_close(speed: int = 80):
    return slow_servo(Defs.pom_grab, 0, speed)

@dsl
def servo_pom_grab_pom_width(speed: int = 120): #open die claw only a bit wider as a pom diameter
    return slow_servo(Defs.pom_grab, 55, speed)

@dsl
def servo_pom_grab_slightly_open(speed: int = 120):
    return slow_servo(Defs.pom_grab, 75, speed)

@dsl
def servo_pom_grab_open(speed: int = 120):
    return slow_servo(Defs.pom_grab, 90, speed)

@dsl
def servo_pom_grab_wide_open(speed: int = 120):
    return slow_servo(Defs.pom_grab, 125, speed)

# --- shild servo ---
@dsl
def servo_shield_down(speed: int = 300):
    return slow_servo(Defs.shild, 156, speed)

@dsl
def servo_shield_up(speed: int = 300):
    return slow_servo(Defs.shild, 86, speed)


# --- shild graber serbo ---
@dsl
def servo_shield_grabber_open():
    return servo(Defs.shild_graber, 90)


@dsl
def servo_shield_grabber_close():
    return servo(Defs.shild_graber, 17)
