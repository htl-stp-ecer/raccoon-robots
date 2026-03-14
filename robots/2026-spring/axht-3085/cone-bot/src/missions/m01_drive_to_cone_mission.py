from libstp import *

class M01DriveToConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            turn_right(deg=65),
            drive_forward(cm=41),
            # turn_right(deg=90),
            # drive_forward(cm=46),
            # forward_lineup_on_black(),
            # drive_forward(cm=41),
            # forward_lineup_on_black(),
            # turn_left(deg=180),
            # drive_forward(cm=93),
            # turn_left(deg=91),
            # drive_forward(cm=5),
            # forward_lineup_on_black(),
            # turn_right(deg=1),
            # drive_forward(cm=34),
            # turn_left(deg=91),
            # drive_forward(cm=3),
            # forward_lineup_on_black(),
            # follow_line(cm=146)
        ])
