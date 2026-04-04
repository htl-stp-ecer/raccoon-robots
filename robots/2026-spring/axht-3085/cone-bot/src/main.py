from src.hardware.robot import Robot

from .missions.m040_drive_to_ramp_mission import M040DriveToRampMission
robot = Robot()

if __name__ == "__main__":
    robot.start()
