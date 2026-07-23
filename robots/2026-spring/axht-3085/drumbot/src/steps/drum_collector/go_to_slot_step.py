from raccoon import GenericRobot, dsl
from raccoon.step import Step

from src.service.drum_motor_service import DrumMotorService, MotorStalledError, NUM_POCKETS


@dsl(hidden=True)
class GoToSlotStep(Step):
    """Rotate the revolver to a specific slot via the shortest path.

    Takes the shortest direction regardless of which slots are filled —
    it does NOT route around occupied slots.

    Optional stall handling:
      - ``stall_retries``: temporarily override the service's stall-retry
        budget for this move only (restored afterwards). Use ``1`` for a
        single attempt with no back-up-and-retry.
      - ``tolerate_stall``: if the move stalls (after the retry budget is
        exhausted), brake and continue instead of re-raising — the revolver
        simply stays where it stalled.
    """

    def __init__(
        self,
        slot: int,
        *,
        stall_retries: int | None = None,
        tolerate_stall: bool = False,
    ):
        super().__init__()
        self.slot = slot % NUM_POCKETS
        self.stall_retries = stall_retries
        self.tolerate_stall = tolerate_stall

    async def _execute_step(self, robot: "GenericRobot") -> None:
        drum_service = robot.get_service(DrumMotorService)
        drum_service.info(
            f"Going to slot {self.slot} from pocket {drum_service.current_pocket}"
        )
        prior = drum_service.stall_retries
        if self.stall_retries is not None:
            drum_service.stall_retries = self.stall_retries
        try:
            await drum_service.go_to_pocket(self.slot, precise=False)
        except MotorStalledError as e:
            if not self.tolerate_stall:
                raise
            drum_service.motor.brake()
            drum_service.warn(
                f"go_to_slot({self.slot}) stalled — not rotating there, continuing: {e}"
            )
        finally:
            if self.stall_retries is not None:
                drum_service.stall_retries = prior


@dsl()
def go_to_slot(
    slot: int,
    *,
    stall_retries: int | None = None,
    tolerate_stall: bool = False,
) -> GoToSlotStep:
    """Rotate the revolver to the given slot via the shortest path."""
    return GoToSlotStep(
        slot=slot,
        stall_retries=stall_retries,
        tolerate_stall=tolerate_stall,
    )
