from libstp import GenericRobot, dsl
from libstp.ui.step import UIStep

from src.service.drum_motor_service import DrumMotorService

from .screens import SortIntoSlotOffsetScreen


@dsl(hidden=True)
class SortIntoSlotCalibrationStep(UIStep):
    """Run the same drum motion pattern as SortIntoSlot, without color sorting."""

    def __init__(self, pocket_count: int = 1) -> None:
        super().__init__()
        self.pocket_count = pocket_count

    async def _execute_step(self, robot: "GenericRobot") -> None:
        drum_service = robot.get_service(DrumMotorService)

        drum_service.info(
            "Sort-into-slot calibration: "
            f"forward {self.pocket_count} pocket(s); "
            f"backward {self.pocket_count} pocket(s)",
        )

        for i in range(self.pocket_count):
            await drum_service.advance(1)
        await self.show(
            SortIntoSlotOffsetScreen(
                heading="Forward Pocket Reached",
                message=(
                    f"The revolver moved forward by {self.pocket_count} pocket(s). "
                    "Press the button to return."
                ),
            ),
        )

        for i in range(self.pocket_count):
            await drum_service.retreat(1)
        await self.show(
            SortIntoSlotOffsetScreen(
                heading="Backward Pocket Reached",
                message=(
                    f"The revolver moved backward by {self.pocket_count} pocket(s). "
                    "Press the button to continue."
                ),
            ),
        )


@dsl()
def calibrate_sort_into_slot(
    pocket_count: int = 1,
) -> SortIntoSlotCalibrationStep:
    """Move the revolver forward and back to verify edge alignment."""
    return SortIntoSlotCalibrationStep(
        pocket_count=pocket_count,
    )
