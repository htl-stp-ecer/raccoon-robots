from libstp.ui import *

from src.ui.widgets import CamFeed


class BaselineScreen(UIScreen[bool]):
    """Simple capture screen: camera feed + instruction + badge.

    Shows the camera feed and waits for the user to confirm before the
    caller grabs a single frame.  Closes with ``True`` on confirm or
    ``False`` if the user skips.
    """

    _primary_button_id = "capture"

    def __init__(self, instruction: str, badge: str):
        super().__init__()
        self.title = "Color Calibration"
        self.instruction = instruction
        self.badge = badge

    def build(self) -> Widget:
        badge_color = "blue" if self.badge.lower() == "blue" else (
            "orange" if self.badge.lower() == "pink" else "grey"
        )

        right = [
            Row(children=[
                StatusBadge(self.badge.upper(), color=badge_color),
            ], align="center"),
            Spacer(height=12),
            Text(self.instruction, size="large", align="center"),
            Spacer(height=12),
            HintBox("Point the camera, then press Capture.", icon="camera_alt"),
            Spacer(height=16),
            Row(children=[
                Button("skip", "Skip", style="secondary"),
                Button("capture", "Capture", style="success"),
            ], align="center", spacing=12),
        ]

        return Split(
            left=[CamFeed()],
            right=right,
            ratio=(3, 2),
        )

    @on_click("capture")
    async def on_capture(self):
        self.close(True)

    @on_click("skip")
    async def on_skip(self):
        self.close(False)
