from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.service.sorting_service import SortingService


@dsl(hidden=True)
class PrefillDrumsStep(Step):
    """Pre-populate the sorting service as if drums were already collected."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        sorting = robot.get_service(SortingService)

        # Slots 0-3: blue, slots 4-7: pink
        for i in range(4):
            sorting.assign_slot("blue")
        for i in range(4):
            sorting.assign_slot("pink")

        self.info(f"Prefilled drums: {sorting.slots}")


@dsl()
def prefill_drums() -> PrefillDrumsStep:
    """Set drum slots to: 0-3 blue, 4-7 pink."""
    return PrefillDrumsStep()
