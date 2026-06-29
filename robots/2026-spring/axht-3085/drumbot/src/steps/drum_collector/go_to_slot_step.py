from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.service.drum_motor_service import DrumMotorService, NUM_POCKETS


@dsl(hidden=True)
class GoToSlotStep(Step):
    """Rotate the revolver to a specific slot via the shortest path.

    Takes the shortest direction regardless of which slots are filled —
    it does NOT route around occupied slots.
    """

    def __init__(self, slot: int):
        super().__init__()
        self.slot = slot % NUM_POCKETS

    async def _execute_step(self, robot: "GenericRobot") -> None:
        drum_service = robot.get_service(DrumMotorService)
        drum_service.info(
            f"Going to slot {self.slot} from pocket {drum_service.current_pocket}"
        )
        await drum_service.go_to_pocket(self.slot, precise=False)


@dsl()
def go_to_slot(slot: int) -> GoToSlotStep:
    """Rotate the revolver to the given slot via the shortest path."""
    return GoToSlotStep(slot=slot)
