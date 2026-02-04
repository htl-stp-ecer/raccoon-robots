from libstp.mission.api import Mission
from libstp.step.sequential import Sequential, seq
from libstp.step.motion.drive import drive_forward

class TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(cm=10, velocity=1)
        ])
