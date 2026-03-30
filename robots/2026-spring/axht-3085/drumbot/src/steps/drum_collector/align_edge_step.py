from libstp import GenericRobot, dsl
from libstp.ui.step import UIStep

from src.service.drum_motor_service import DrumMotorService

from .screens import EdgeAlignScreen


@dsl(hidden=True)
class AlignEdgeStep(UIStep):
    """Advance one pocket and let the user confirm before resetting to pocket 0.

    1. Advance one pocket so the sensor lands on black.
    2. Show UI so the user can nudge forward/backward.
    3. On confirm, reset position to pocket 0.
    """

    async def _execute_step(self, robot: "GenericRobot") -> None:
        drum = robot.get_service(DrumMotorService)

        await drum.advance(1)

        # Let the user verify and nudge if needed
        await self.show(EdgeAlignScreen(drum))

        # Lock in pocket 0
        drum.reset_position(0)
        drum.info("Alignment confirmed — position reset to pocket 0")


@dsl()
def align_edge() -> AlignEdgeStep:
    """Align the drum to a pocket and reset position to pocket 0."""
    return AlignEdgeStep()
