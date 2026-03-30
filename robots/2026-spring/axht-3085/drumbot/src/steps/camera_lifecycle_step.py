from libstp import GenericRobot, dsl
from libstp.step import Step

from src.service.color_detection_service import ColorDetectionService


@dsl(hidden=True)
class StartCameraStep(Step):
    async def _execute_step(self, robot: "GenericRobot") -> None:
        robot.get_service(ColorDetectionService).start_camera()


@dsl(hidden=True)
class StopCameraStep(Step):
    async def _execute_step(self, robot: "GenericRobot") -> None:
        robot.get_service(ColorDetectionService).stop_camera()


@dsl()
def start_camera() -> StartCameraStep:
    return StartCameraStep()


@dsl()
def stop_camera() -> StopCameraStep:
    return StopCameraStep()
