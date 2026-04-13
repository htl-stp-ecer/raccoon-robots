from raccoon.ui import *


class EmergencyScreen(UIScreen[bool]):
    """Motor stuck: countdown to shutdown with option to continue the run."""

    title = "EMERGENCY"
    _primary_button_id = "continue"

    def __init__(self):
        super().__init__()
        self.seconds_left: int = 15
        self.reason: str = "Drum Motor is stuck."

    def build(self) -> Widget:
        return Center(children=[
            Column(children=[
                Text("EMERGENCY", size="title", bold=True, color="#FF0000"),
                Spacer(height=16),
                Text(
                    f"Failed! {self.reason}",
                    size="large",
                    align="center",
                ),
                Spacer(height=12),
                Text(
                    f"Shutting down in {self.seconds_left}s!",
                    size="large",
                    align="center",
                    color="#FF4444",
                ),
                Spacer(height=8),
                Text(
                    "Click button to continue run",
                    size="medium",
                    align="center",
                    muted=True,
                ),
                Spacer(height=24),
                Button(
                    id="continue",
                    label="Continue Run",
                    style="success",
                ),
            ]),
        ])

    @on_click("continue")
    async def _on_continue(self):
        self.close(True)
