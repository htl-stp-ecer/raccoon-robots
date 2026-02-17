import libstp.foundation as logging

from src.hardware.robot import Robot
from .missions.grab_first_poms_mission import GrabFirstPomsMission

# logging.set_global_level(logging.Level.debug)
# logging.set_file_level("turn.py", logging.Level.trace)
# logging.set_file_level("turn_motion.cpp", logging.Level.trace)
# logging.set_file_level("fused_odometry.cpp", logging.Level.info)

robot = Robot()
robot.missions = [
    GrabFirstPomsMission()
]

if __name__ == "__main__":
    robot.start()
