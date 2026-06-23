from raccoon.ui import *


class EmergencyScreen(UIScreen[bool]):
    """Drum fault: informational only. The robot is autonomous — there is no
    user input. Collection is abandoned, the big drum is disabled, and the run
    continues on its path; this screen is held until the post-collection
    checkpoint releases it.
    """

    title = "EMERGENCY"

    def __init__(self):
        super().__init__()
        self.seconds_left: int = 0  # seconds until the run continues
        self.reason: str = "Drum motor fault."

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
                    "Big drum disabled — continuing run to protect hardware",
                    size="medium",
                    align="center",
                    color="#FF4444",
                ),
                Spacer(height=8),
                Text(
                    f"Resuming path in {self.seconds_left}s",
                    size="medium",
                    align="center",
                    muted=True,
                ),
            ]),
        ])
