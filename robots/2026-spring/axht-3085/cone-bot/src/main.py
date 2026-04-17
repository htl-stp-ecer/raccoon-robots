from src.hardware.robot import Robot

from .missions.m040_drive_to_ramp_mission import M040DriveToRampMission
from .missions.m050_drive_to_starting_box_mission import M050DriveToStartingBoxMission
from .missions.m060_drop_conees_mission import M060DropConeesMission
from .missions.m001_drive_down_ramp_mission import M001DriveDownRampMission
robot = Robot()

if __name__ == "__main__":
    robot.start()
