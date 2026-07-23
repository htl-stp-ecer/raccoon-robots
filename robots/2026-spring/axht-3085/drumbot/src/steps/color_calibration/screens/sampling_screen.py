from raccoon.ui import *

from src.ui.widgets import CamFeed


class SamplingScreen(UIScreen[bool]):
    """Split-screen: tappable camera feed (left) + sampling status (right).

    The user taps on the drum in the camera feed to define the sampling
    region. HSV values are collected from that region.
    """

    _primary_button_id = "confirm"

    def __init__(self, color_name: str, instruction: str):
        super().__init__()
        self.title = "Color Calibration"
        self.color_name = color_name
        self.instruction = instruction
        self.h_mean: float = 0
        self.s_mean: float = 0
        self.v_mean: float = 0
        self.sample_count: int = 0
        self.sampling = False
        self.tap_x: float | None = None
        self.tap_y: float | None = None

    def build(self) -> Widget:
        badge_color = "blue" if self.color_name == "blue" else "orange"

        right_children = [
            Row(children=[
                StatusBadge(self.color_name.upper(), color=badge_color, glow=self.sampling),
            ], align="center"),
            Text(self.instruction, size="large", align="center"),
            Spacer(height=8),
        ]

        if self.tap_x is None:
            right_children.append(
                HintBox("Tap on the drum in the camera feed", icon="touch_app"),
            )
        elif self.sample_count > 0:
            right_children.append(
                Card(title="HSV Sample", children=[
                    ResultsTable(rows=[
                        ("Hue", f"{self.h_mean:.0f}", None),
                        ("Saturation", f"{self.s_mean:.0f}", None),
                        ("Value", f"{self.v_mean:.0f}", None),
                        ("Frames", f"{self.sample_count}", None),
                    ]),
                ]),
            )
        else:
            right_children.append(
                HintBox("Collecting samples...", icon="camera_alt"),
            )

        right_children.extend([
            Spacer(height=8),
            Row(children=[
                Button("skip", "Skip", style="secondary"),
                Button("confirm", "Confirm",
                       style="success",
                       disabled=self.tap_x is None),
            ], align="center", spacing=12),
        ])

        return Split(
            left=[CamFeed(id="cam_tap", tappable=True)],
            right=right_children,
            ratio=(3, 2),
        )

    @on_change("cam_tap")
    async def on_tap(self, value):
        if isinstance(value, dict):
            self.tap_x = value.get("x")
            self.tap_y = value.get("y")
            self.sample_count = 0
            await self.refresh()

    @on_click("confirm")
    async def on_confirm(self):
        self.close(True)

    @on_click("skip")
    async def on_skip(self):
        self.close(False)
