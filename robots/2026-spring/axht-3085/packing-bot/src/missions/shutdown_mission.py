from libstp import Mission, Sequential, seq


class ShutdownMission(Mission):
    def sequence(self) -> Sequential:
        return seq([])
