from libstp import Mission, seq, turn_left, drive_forward


class drive_to_Drum_dispenser(Mission):
    def sequnce (self):
        return seq([
            drive_forward(10,1),
            turn_left(30),

        ])