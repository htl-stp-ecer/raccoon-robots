from libstp import *
from src.hardware.defs import *


@dsl
def frontside_forward_lineup_on_black(threshold = 0.7):
    return forward_lineup_on_black(Defs.front_left_light_sensor, Defs.front_right_light_sensor, detection_threshold=threshold)

@dsl
def simpl_frontside_forward_lineup_on_black(threshold = 0.7):
    return lineup(
        left_sensor=Defs.front_left_light_sensor,
        right_sensor=Defs.front_right_light_sensor,
        target=SurfaceColor.BLACK,
        detection_threshold=threshold
    )

@dsl
def frontside_forward_drive_until_line(threshold = 0.7):
    return drive_forward_until_black([Defs.front_left_light_sensor, Defs.front_right_light_sensor], speed = 1.0, confidence_threshold=threshold)

@dsl
def frontside_forward_lineup_on_white():
    return forward_lineup_on_white(Defs.front_left_light_sensor, Defs.front_right_light_sensor)



@dsl
def frontside_backward_lineup_on_black():
    return backward_lineup_on_black(Defs.front_left_light_sensor, Defs.front_right_light_sensor)

@dsl
def frontside_backward_lineup_on_white():
    return backward_lineup_on_white(Defs.front_left_light_sensor, Defs.front_right_light_sensor)


def frontside_line_follow():
    #follow_line(Defs.)
    pass

@dsl
def frontside_line_follow_right_edge(cm, speed = 1.0):
    #return follow_line_single_right_edge(Defs.front_right_light_sensor, cm, speed)
    pass

@dsl
def left_starfe_until_black(threshold = 0.7, speed = 1.0):
    return strafe_left_until_black(Defs.front_left_light_sensor,
                                       speed = speed,
                                       confidence_threshold=threshold)
