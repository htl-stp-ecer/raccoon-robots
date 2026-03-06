from src.hardware.defs import *
from libstp import lineup, SurfaceColor, drive_forward_until_black, forward_lineup_on_white, forward_lineup_on_black, \
    backward_lineup_on_black, backward_lineup_on_white, dsl, strafe_left_lineup_on_black, strafe_left_until_black, \
    follow_line_single_until_black, LineSide, drive_forward_until_white, seq, follow_line_single, \
    drive_backward_until_black


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
def frontside_forward_drive_over_line(threshold = 0.7):
    return seq([
            drive_forward_until_black([Defs.front_left_light_sensor, Defs.front_right_light_sensor], speed = 1.0, confidence_threshold=threshold),
            drive_forward_until_white([Defs.front_left_light_sensor, Defs.front_right_light_sensor], speed = 1.0, confidence_threshold=threshold),
        ])

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
    return follow_line_single(
        Defs.front_right_light_sensor,
        cm,
        0.8,
        side=LineSide.RIGHT,
        kp=0.5,
        ki=0.02,
        kd=0,
    )

def single_line_follow_right_front_edge_until_line(speed = 1.0, threshold = 0.7):
    return follow_line_single_until_black(
        Defs.front_right_light_sensor,
        Defs.front_left_light_sensor,
        0.8,
        side=LineSide.RIGHT,
        stop_threshold=1.0,
        kp=0.5,
        ki=0.02,
        kd=0,
    )

@dsl
def left_starfe_until_black(threshold = 0.7, speed = 1.0):
    return strafe_left_until_black(Defs.front_left_light_sensor,
                                       speed = speed,
                                       confidence_threshold=threshold)

def backside_backward_drive_until_line(threshold = 0.7):
    return drive_backward_until_black(Defs.rear_right_light_sensor,
                                      speed = 1.0,
                                      treshold=threshold,)
