from libstp import *

class M01DriveToConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
             drive_forward(73),
        ])
