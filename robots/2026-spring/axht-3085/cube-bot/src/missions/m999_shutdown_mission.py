from raccoon import Mission, Sequential, seq

from src.hardware.defs import Defs


class M999ShutdownMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            Defs.arm_claw.open(),
        ])
