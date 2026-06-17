from src.patches.heading_frame import apply as _apply_heading_patch

_apply_heading_patch()

import os

from src.hardware.robot import Robot

def main():
    robot = Robot()

    if os.getenv("DRUMBOT_FAKE_CAMERA") == "1":
        from src.service.fake_color_detection_service import install_fake_color_service
        install_fake_color_service(robot)

    robot.start()

if __name__ == "__main__":
    main()
