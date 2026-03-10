from libstp.mission.api import Mission
from libstp.step.sequential import Sequential, seq

class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            calibrate(distance=50)
        ])
