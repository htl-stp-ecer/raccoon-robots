from raccoon.ui import *

from src.ui.widgets import CamFeed


class ColorCapturingScreen(UIScreen[None]):
    """Screen shown after Capture is pressed while fresh frames are recorded."""

    title = "Color Calibration"

    def __init__(self, instruction: str, badge: str):
        super().__init__()
        self.instruction = instruction
        self.badge = badge

    def build(self) -> Widget:
        badge_color = "blue" if self.badge.lower() == "blue" else (
            "orange" if self.badge.lower() == "pink" else "grey"
        )

        return Split(
            left=[CamFeed(show_detections=False)],
            right=[
                Row(children=[
                    StatusBadge(self.badge.upper(), color=badge_color, glow=True),
                ], align="center"),
                Spacer(height=12),
                Row(children=[
                    ProgressSpinner(size=24),
                    Spacer(8),
                    Text("Capturing...", size="large"),
                ], align="center"),
                Spacer(height=12),
                Text(self.instruction, size="small", align="center", muted=True),
                Spacer(height=12),
                HintBox("Hold the scene steady. Recording fresh camera frames.", icon="camera_alt"),
            ],
            ratio=(3, 2),
        )
