from libstp.ui import *

from src.ui.widgets import CamFeed


class BaselineScreen(UIScreen[bool]):
    """Split-screen: live feed (left) + baseline sampling status (right).

    Shown when the camera view should be empty so we can measure the
    background HSV distribution and exclude it from color ranges.
    """

    _primary_button_id = "confirm"

    def __init__(self):
        super().__init__()
        self.title = "Color Calibration"
        self.sample_count: int = 0
        self.blue_noise: int = 0
        self.pink_noise: int = 0
        self.sampling = False

    def build(self) -> Widget:
        right = [
            Row(children=[
                StatusBadge("BASELINE", color="grey", glow=self.sampling),
            ], align="center"),
            Text("Remove all drums from view", size="large", align="center"),
            Spacer(height=8),
            HintBox(
                "Clear the camera view completely. "
                "The background will be measured and excluded "
                "from color detection.",
                icon="visibility_off",
            ),
            Spacer(height=8),
        ]

        if self.sample_count > 0:
            right.append(
                Card(title="Background Sample", children=[
                    Text(f"{self.sample_count} frames captured", size="medium"),
                    Text(
                        "Background HSV will be excluded from color ranges",
                        size="small", muted=True,
                    ),
                ]),
            )

        right.extend([
            Spacer(height=8),
            Button("confirm", "Confirm", style="success"),
        ])

        return Split(
            left=[CamFeed()],
            right=right,
            ratio=(3, 2),
        )

    @on_click("confirm")
    async def on_confirm(self):
        self.close(True)
