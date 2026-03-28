from libstp import Mission, Sequential, seq


class M999ShutdownMission(Mission):
    def sequence(self) -> Sequential:
        return seq([])
