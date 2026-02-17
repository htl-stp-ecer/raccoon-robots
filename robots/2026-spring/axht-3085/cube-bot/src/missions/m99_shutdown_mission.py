from libstp import Mission, Sequential, seq


class M99ShutdownMission(Mission):
    def sequence(self) -> Sequential:
        return seq([])
