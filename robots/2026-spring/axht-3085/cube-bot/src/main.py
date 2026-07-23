from src.hardware.robot import Robot
import raccoon.foundation as logging


def main():
    robot = Robot()
    robot.start()

if __name__ == "__main__":
    main()
