import os

from raccoon import GenericRobot, UIStep, dsl
from src.ui.position_hold_choice_screen import PositionHoldChoiceScreen

from src.steps.set_position_hold_velocity_step import POSITION_HOLD_ENV


@dsl(hidden=True)
class PositionHoldChoiceStep(UIStep):
    """Ask the operator whether to use position holding during collection.

    Position holding is controlled globally by the POSITION_HOLD_ENV env var
    (set = disabled). Primary button keeps it enabled, secondary disables it.
    """

    async def _execute_step(self, robot: "GenericRobot") -> None:
        use_hold = await self.show(PositionHoldChoiceScreen(
            title="Position Hold",
            message="Use position holding during drum collection?",
            confirm_label="Use it",
            cancel_label="Don't use",
            confirm_style="success",
            icon_name="anchor",
            icon_color="blue",
        ))

        if use_hold:
            os.environ.pop(POSITION_HOLD_ENV, None)
            self.info("Position holding ENABLED")
        else:
            os.environ[POSITION_HOLD_ENV] = "1"
            self.info("Position holding DISABLED")


@dsl()
def choose_position_hold() -> PositionHoldChoiceStep:
    return PositionHoldChoiceStep()
