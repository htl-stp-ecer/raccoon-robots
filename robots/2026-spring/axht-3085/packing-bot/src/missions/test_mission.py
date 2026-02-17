from libstp.mission.api import Mission
from libstp.step.motion.drive import drive_forward
from libstp.step.sequential import Sequential, seq


class TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(cm=10, velocity=1)
        ])
