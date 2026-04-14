from src.hardware.robot import Robot

from .missions.m1009_test_mission import M1009TestMission
robot = Robot()

if __name__ == "__main__":
    robot.start()
