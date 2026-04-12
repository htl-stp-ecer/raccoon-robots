import asyncio

from raccoon import GenericRobot, dsl, UIStep
from raccoon.step import Step
from raccoon.ui.screen import UIScreen
from raccoon.ui.widgets import Center, Column, Spacer, StatusBadge, Text, Widget

from src.service.color_detection_service import ColorDetectionService


class CameraStartingScreen(UIScreen[None]):
    title = "Camera"

    def build(self) -> Widget:
        return Center(children=[
            Column(children=[
                StatusBadge("STARTING", color="grey", glow=True),
                Spacer(height=16),
                Text("Camera is warming up...", size="large", align="center"),
                Spacer(height=8),
                Text("This may take a few seconds.", size="small", align="center", color="#888888"),
            ]),
        ])


@dsl(hidden=True)
class StartCameraStep(UIStep):
    async def _execute_step(self, robot: "GenericRobot") -> None:
        screen = CameraStartingScreen()
        service = robot.get_service(ColorDetectionService)

        service.annotate_detections = True

        async def _start_and_close():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, service.start_camera)
            screen.close(None)

        asyncio.create_task(_start_and_close())
        await self.show(screen)


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
