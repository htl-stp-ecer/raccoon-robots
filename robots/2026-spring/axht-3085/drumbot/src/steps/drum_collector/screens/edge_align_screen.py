from libstp.ui import *

from src.service.drum_motor_service import DrumMotorService


class EdgeAlignScreen(UIScreen[bool]):
    """Let the user visually confirm pocket alignment before resetting to pocket 0."""

    title = "Pocket Alignment"
    _primary_button_id = "confirm"

    def __init__(self, drum_service: DrumMotorService):
        super().__init__()
        self.drum_service = drum_service

    def build(self) -> Widget:
        pocket = self.drum_service.current_pocket
        return Column(children=[
            Row(children=[
                StatusIcon(icon="target", color="blue"),
                Spacer(8),
                Text("Align pocket opening, then confirm", size="large"),
            ], align="center"),
            Spacer(12),
            ResultsTable(rows=[
                ("Current pocket", str(pocket), "blue"),
            ]),
            Spacer(16),
            Row(children=[
                Button("nudge_back", "Nudge back", style="secondary"),
                Button("nudge_fwd", "Nudge forward", style="secondary"),
                Button("confirm", "Set as pocket 0", style="success"),
            ], spacing=8),
        ])

    @on_click("nudge_back")
    async def on_nudge_back(self):
        await self.drum_service.retreat(1)
        await self.refresh()

    @on_click("nudge_fwd")
    async def on_nudge_fwd(self):
        await self.drum_service.advance(1)
        await self.refresh()

    @on_click("confirm")
    async def on_confirm(self):
        self.close(True)
