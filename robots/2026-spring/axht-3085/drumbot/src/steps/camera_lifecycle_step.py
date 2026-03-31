from libstp import GenericRobot, UIStep, dsl
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


@dsl(hidden=True)
class CameraTestLoopStep(UIStep):
    """Press button to print last detected color. Keeps looping until stopped."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        color_service = robot.get_service(ColorDetectionService)
        while True:
            await self.wait_for_button("Press button to detect color (hold to exit)")
            color = await color_service.detect_color()
            color_service.info(f">>> Detected: {color or 'NONE'} <<<")


@dsl()
def start_camera() -> StartCameraStep:
    return StartCameraStep()


@dsl()
def stop_camera() -> StopCameraStep:
    return StopCameraStep()


@dsl()
def camera_test_loop() -> CameraTestLoopStep:
    return CameraTestLoopStep()
