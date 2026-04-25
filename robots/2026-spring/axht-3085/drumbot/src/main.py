from src.hardware.robot import Robot

from .missions.m1009_test_mission import M1009TestMission


def main():
    robot = Robot()
    robot.start()


if __name__ == "__main__":
    main()
