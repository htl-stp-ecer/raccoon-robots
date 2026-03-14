from libstp import *

from src.hardware.defs import Defs


class M03CollectBotguyMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            turn_left(90),
        ])