from libstp import *
from libstp.step.servo import slow_servo

from src.hardware.defs import *

# --- pom arm ---
def servo_pom_arm_down():
    return slow_servo(Defs.pom_arm, 0, 1)

def servo_pom_arm_up():
    return slow_servo(Defs.pom_arm, 60, 1)

def servo_pom_arm_start():
    return slow_servo(Defs.pom_arm, 120, 5)

# --- pom grab ---
def servo_pom_grab_close():
    return slow_servo(Defs.pom_grab, 0, 0.7)

def servo_pom_grab_open():
    return slow_servo(Defs.pom_grab, 70, 0.7)
