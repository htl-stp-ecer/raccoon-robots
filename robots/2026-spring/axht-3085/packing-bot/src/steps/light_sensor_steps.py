from libstp import *
from src.hardware.defs import *

@dsl
def frontside_forward_lineup_on_black(threshold = 0.4):
    return forward_lineup_on_black(Defs.front_left_light_sensor, Defs.front_right_light_sensor, detection_threshold=threshold)

@dsl
def simpl_frontside_forward_lineup_on_black(threshold = 0.4):
    return lineup(
        left_sensor=Defs.front_left_light_sensor,
        right_sensor=Defs.front_right_light_sensor,
        target=SurfaceColor.BLACK,
        detection_threshold=threshold
    )

@dsl
def frontside_forward_lineup_on_white():
    return forward_lineup_on_white(Defs.front_left_light_sensor, Defs.front_right_light_sensor)

@dsl
def backside_forward_lineup_on_black():
    return forward_lineup_on_black(Defs.rear_left_light_sensor, Defs.rear_right_light_sensor)

@dsl
def backside_forward_lineup_on_white():
    return forward_lineup_on_white(Defs.rear_left_light_sensor, Defs.rear_right_light_sensor)

@dsl
def frontside_backward_lineup_on_black():
    return backward_lineup_on_black(Defs.front_left_light_sensor, Defs.front_right_light_sensor)

@dsl
def frontside_backward_lineup_on_white():
    return backward_lineup_on_white(Defs.front_left_light_sensor, Defs.front_right_light_sensor)

@dsl
def backside_backward_lineup_on_black():
    return backward_lineup_on_black(Defs.rear_left_light_sensor, Defs.rear_right_light_sensor)

@dsl
def backside_backward_lineup_on_white():
    return backward_lineup_on_white(Defs.rear_left_light_sensor, Defs.rear_right_light_sensor)

def frontside_line_follow():
    #follow_line(Defs.)
    pass
