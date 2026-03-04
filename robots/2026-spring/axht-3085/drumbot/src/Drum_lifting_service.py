from math import degrees

from libstp import slow_servo

from src.hardware import defs


class DrumLiftingService:
    def __init__(self):
        self.degrees = degrees
        self.speed = speed          #in degrees per second

    def move(self):
        slow_servo(defs.drum_pusher_servo ,self.degrees,)
        return


def DrumLiftingServiceUP() -> DrumLiftingService:
    service = DrumLiftingService.move
    return DrumLiftingService(degrees=170, speed=10)


def DrumLiftingServiceMiddle() -> DrumLiftingService:

    return DrumLiftingService(degrees=70, speed=10)

def DrumLiftingServiceDown() -> DrumLiftingService:

    return DrumLiftingService(degrees=20, speed=10)

