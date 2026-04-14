"""Step that installs FakeColorDetectionService — use in place of start_camera()."""

from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.service.fake_color_detection_service import install_fake_color_service


@dsl(hidden=True)
class StartFakeCameraStep(Step):
    async def _execute_step(self, robot: GenericRobot) -> None:
        install_fake_color_service(robot)


@dsl()
def start_fake_camera() -> StartFakeCameraStep:
    return StartFakeCameraStep()
