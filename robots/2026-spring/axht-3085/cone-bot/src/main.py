from src.hardware.robot import Robot

from .missions.m02_collect_cone_mission import M02CollectConeMission
robot = Robot()

if __name__ == "__main__":
    robot.start()
