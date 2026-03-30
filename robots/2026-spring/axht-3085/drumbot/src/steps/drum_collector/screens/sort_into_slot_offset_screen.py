from libstp.ui import *


class SortIntoSlotOffsetScreen(UIScreen[None]):
    title = "Sort Into Slot Calibration"

    def __init__(self, heading: str, message: str):
        super().__init__()
        self.heading = heading
        self.message = message

    def build(self) -> Widget:
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
                Button("continue", "Continue", style="primary"),
            ],
            ratio=(1, 1),
        )

    @on_click("continue")
    async def on_continue(self):
        self.close(None)
