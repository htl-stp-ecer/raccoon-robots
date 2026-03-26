from libstp import GenericRobot, dsl
from libstp.ui.step import UIStep

from src.service.drum_motor_service import DrumMotorService
from .screens import SortIntoSlotOffsetScreen


@dsl(hidden=True)
class SortIntoSlotCalibrationStep(UIStep):
    """Run the same drum motion pattern as SortIntoSlot, without color sorting."""

    def __init__(
        self,
        pocket_count: int = 1,
        offset_forward_ticks: int = 0,
        offset_backward_ticks: int = 0,
        offset_velocity: int = 400,
    ) -> None:
        super().__init__()
        self.pocket_count = pocket_count
        self.offset_forward_ticks = offset_forward_ticks
        self.offset_backward_ticks = offset_backward_ticks
        self.offset_velocity = offset_velocity

    async def _execute_step(self, robot: "GenericRobot") -> None:
        drum_service = robot.get_service(DrumMotorService)

        drum_service.info(
            "Sort-into-slot calibration: "
            f"forward {self.pocket_count} pocket(s), offset={self.offset_forward_ticks}; "
            f"backward {self.pocket_count} pocket(s), offset={self.offset_backward_ticks}"
        )

        await drum_service.advance(self.pocket_count)
        await self.show(
            SortIntoSlotOffsetScreen(
                heading="Forward Pocket Reached",
                message=(
                    f"The revolver moved forward by {self.pocket_count} pocket(s). "
                    "Press the button to apply the forward offset."
                ),
                offset_ticks=self.offset_forward_ticks,
            )
        )
        if self.offset_forward_ticks != 0:
            await drum_service.add_offset(
                self.offset_forward_ticks,
                velocity=self.offset_velocity,
            )
        await self.show(
            SortIntoSlotOffsetScreen(
                heading="Forward Offset Applied",
                message=(
                    "The forward offset is done. Press the button to return to "
                    "the pocket position and start the backward move."
                ),
            )
        )
        if self.offset_forward_ticks != 0:
            await drum_service.add_offset(
                -self.offset_forward_ticks,
                velocity=self.offset_velocity,
            )

        await drum_service.retreat(self.pocket_count)
        await self.show(
            SortIntoSlotOffsetScreen(
                heading="Backward Pocket Reached",
                message=(
                    f"The revolver moved backward by {self.pocket_count} pocket(s). "
                    "Press the button to apply the backward offset."
                ),
                offset_ticks=self.offset_backward_ticks,
            )
        )
        if self.offset_backward_ticks != 0:
            await drum_service.add_offset(
                self.offset_backward_ticks,
                velocity=self.offset_velocity,
            )


@dsl()
def calibrate_sort_into_slot(
    pocket_count: int = 1,
    offset_forward_ticks: int = 0,
    offset_backward_ticks: int = 0,
    offset_velocity: int = 1500,
) -> SortIntoSlotCalibrationStep:
    """Move the revolver forward and back to tune SortIntoSlot offsets."""
    return SortIntoSlotCalibrationStep(
        pocket_count=pocket_count,
        offset_forward_ticks=offset_forward_ticks,
        offset_backward_ticks=offset_backward_ticks,
        offset_velocity=offset_velocity,
    )
