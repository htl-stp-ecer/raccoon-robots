from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.service.drum_motor_service import DrumMotorService


@dsl(hidden=True)
class StartEdgeMonitorStep(Step):
    """Start the background edge-counting monitor on the drum motor service."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        service = robot.get_service(DrumMotorService)
        await service.start_edge_monitor()


@dsl()
def start_edge_monitor() -> StartEdgeMonitorStep:
    """Start background edge monitor for continuous pocket tracking."""
    return StartEdgeMonitorStep()
