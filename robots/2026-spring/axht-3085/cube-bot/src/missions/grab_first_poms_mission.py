from libstp import *
from libstp.step.parallel import parallel


class GrabFirstPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # drive infront of poms
            # AutoTuneTurn(angle=90),
            turn_left(90),
            # drive_backward(cm=5),
            # frontside_forward_lineup_on_black(),
            # drive_backward(cm=7),
            # strafe_left(cm=11),

            ## push poms back
            # drive_forward(cm=35),
            # drive_backward(cm=35),

            # servo_pom_grab_open(),
            # servo_pom_arm_down(),

            # TODO: use the nice funktions
            # frontside_forward_move_over_line(forward_speed=1.0),
            # follow_line

            # get poms and close claw
            # drive_forward(cm=20),
            # put the following 3 commands in a parallel if parallel is fixed
            # strafe_until_black(Defs.front_left_light_sensor, 1.0),
            # seq([
            #    servo_pom_grab_close(),
            #    servo_pom_grab_open(),
            # ]),
            # ---
            ##drive_forward(cm=50),

            ##strafe_until_black(Defs.front_left_light_sensor, 1.0),
            ##servo_pom_grab_close(),
            ##servo_pom_arm_up(),
            ##strafe_left(cm=7),

            # drop cube down
            # strafe_right(cm=16),
            # drive_forward(cm=10),

            # TODO do som align on balck line to do shit right?
            # strafe_left(cm=16),
        ])
