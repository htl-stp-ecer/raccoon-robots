from raccoon import GenericRobot, dsl
from raccoon.ui.step import UIStep

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

        await drum.advance(1, precise=True)

        # Let the user verify and nudge if needed
        await self.show(EdgeAlignScreen(drum))

        # Lock in pocket 0 and start the always-on IR tracker. From this
        # point on, every stripe crossing (commanded motion OR coast) updates
        # the pocket index automatically.
        drum.reset_position(0)
        drum.start_position_tracking()
        drum.info("Alignment confirmed — position reset to pocket 0, tracker armed")


@dsl()
def align_edge() -> AlignEdgeStep:
    """Align the drum to a pocket and reset position to pocket 0."""
    return AlignEdgeStep()
