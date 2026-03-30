
from libstp import GenericRobot, dsl
from libstp.step import Step

from src.service.drum_motor_service import DrumMotorService
from src.service.sorting_service import SortingService


@dsl(hidden=True)
class DispenseSortedStep(Step):
    """Drive through all slots of one color sequentially and eject each drum.

    For each slot: go_to(slot), then retreat 1 pocket to push the drum out.
    """

    def __init__(self, color: str):
        super().__init__()
        self.color = color

    async def _execute_step(self, robot: "GenericRobot") -> None:
        sorting = robot.get_service(SortingService)
        drum = robot.get_service(DrumMotorService)

        slots = sorting.blue_slots if self.color == "blue" else sorting.pink_slots
        drum.info(f"Dispensing {self.color}: slots={slots}")

        for slot in slots:
            await drum.go_to_pocket(slot)
            await drum.retreat(1)


@dsl()
def dispense_sorted(color: str) -> DispenseSortedStep:
    """Dispense all drums of the given color sequentially."""
    return DispenseSortedStep(color=color)
