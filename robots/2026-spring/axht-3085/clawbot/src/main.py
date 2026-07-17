from src.hardware.robot import Robot
import raccoon.foundation as logging

#logging.set_file_level("fused_odometry.cpp", logging.Level.trace),
#logging.set_file_level("single_line_follow.py", logging.Level.debug),
#logging.set_file_level("libstp.step.base", logging.Level.debug),

def main():
    robot = Robot()
    robot.start()

if __name__ == "__main__":
    main()
