from libstp.ui import *


class SortIntoSlotOffsetScreen(UIScreen[None]):
    title = "Sort Into Slot Calibration"

    def __init__(self, heading: str, message: str, offset_ticks: int | None = None):
        super().__init__()
        self.heading = heading
        self.message = message
        self.offset_ticks = offset_ticks

    def build(self) -> Widget:
        rows = []
        if self.offset_ticks is not None:
            rows.append(("Offset Ticks", f"{self.offset_ticks}", "orange"))

        return Split(
            left=[
                Row(children=[
                    StatusIcon(icon="pause", color="orange"),
                    Spacer(8),
                    Text(self.heading, size="large"),
                ], align="center"),
                Spacer(8),
                Text(self.message, size="small", muted=True),
            ],
            right=[
                ResultsTable(rows=rows) if rows else Spacer(1),
                Spacer(12),
                Button("continue", "Continue", style="primary"),
            ],
            ratio=(1, 1),
        )

    @on_click("continue")
    async def on_continue(self):
        self.close(None)
