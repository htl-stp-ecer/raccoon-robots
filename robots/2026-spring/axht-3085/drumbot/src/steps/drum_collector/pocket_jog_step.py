from raccoon import GenericRobot, UIStep, dsl
from raccoon.ui import *

from src.service.drum_motor_service import DrumMotorService


class PocketJogScreen(UIScreen[None]):
    """Manually advance or revert the drum one pocket at a time."""

    title = "Drum Pocket Jog"
    _primary_button_id = "done"

    def __init__(self, drum_service: DrumMotorService):
        super().__init__()
        self.drum_service = drum_service

    def build(self) -> Widget:
        return Column(children=[
            Row(children=[
                StatusIcon(icon="target", color="blue"),
                Spacer(8),
                Text("Jog the drum pocket", size="large"),
            ], align="center"),
            Spacer(12),
            ResultsTable(rows=[
                ("Current pocket", str(self.drum_service.current_pocket), "blue"),
            ]),
            Spacer(16),
            Row(children=[
                Button("revert", "Revert", style="secondary"),
                Button("advance", "Advance", style="primary"),
                Button("done", "Done", style="success"),
            ], spacing=8),
        ])

    @on_click("advance")
    async def on_advance(self):
        await self.drum_service.advance(1)
        await self.refresh()

    @on_click("revert")
    async def on_revert(self):
        await self.drum_service.retreat(1)
        await self.refresh()

    @on_click("done")
    async def on_done(self):
        self.close(None)


@dsl(hidden=True)
class PocketJogStep(UIStep):
    async def _execute_step(self, robot: "GenericRobot") -> None:
        service = robot.get_service(DrumMotorService)
        await self.show(PocketJogScreen(service))


@dsl()
def pocket_jog() -> PocketJogStep:
    """Show a screen with Advance / Revert buttons to jog the drum pocket."""
    return PocketJogStep()
