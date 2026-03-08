from libstp.mission.api import Mission
from libstp.step.sequential import Sequential, seq

class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            wait_for_button(),
            calibrate_range_finder(),
            wait_for_button(),
            turn_to_peak()
        ])
