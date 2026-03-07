from libstp import Mission, Sequential, seq

from src.steps.drum_lifting_step import drum_lifting_down


class M02CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drum_lifting_down()
        ])