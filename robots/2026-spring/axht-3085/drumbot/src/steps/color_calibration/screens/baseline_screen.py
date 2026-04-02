from libstp.ui import *

from src.ui.widgets import CamFeed


class BaselineScreen(UIScreen[bool]):
    """Split-screen: live feed (left) + baseline sampling status (right).

    Shown when the camera view should be empty so we can measure the
    background HSV distribution and exclude it from color ranges.
    """

    _primary_button_id = "confirm"

    def __init__(self, instruction: str = "Remove all drums from view", badge: str = "CAPTURE"):
        super().__init__()
        self.title = "Color Calibration"
        self._instruction = instruction
        self._badge = badge

    def build(self) -> Widget:
        right = [
            Row(children=[
                StatusBadge(self._badge, color="grey", glow=False),
            ], align="center"),
            Text(self._instruction, size="large", align="center"),
            Spacer(height=8),
            HintBox(
                "A single frame will be captured when you press Confirm.",
                icon="photo_camera",
            ),
            Spacer(height=8),
        ]

        right.extend([
            Spacer(height=8),
            Button("confirm", "Capture & Confirm", style="success"),
        ])

        return Split(
            left=[CamFeed()],
            right=right,
            ratio=(3, 2),
        )

    @on_click("confirm")
    async def on_confirm(self):
        self.close(True)
