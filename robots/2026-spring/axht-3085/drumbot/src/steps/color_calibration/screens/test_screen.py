from raccoon.ui import *

from src.ui.widgets import CamFeed


class ColorTestScreen(UIScreen[str]):
    """Split-screen: live feed with detections (left) + result display (right).

    Closes with "done" or "retry" (go back to confirm/retry screen).
    """

    _primary_button_id = "done"

    def __init__(self):
        super().__init__()
        self.title = "Color Test"
        self.detected_color: str | None = None
        self.confidence: float = 0.0

    def build(self) -> Widget:
        if self.detected_color:
            badge_color = "blue" if self.detected_color == "blue" else "orange"
            color_text = self.detected_color.upper()
            icon = "check"
            icon_color = "green"
        else:
            badge_color = "grey"
            color_text = "NONE"
            icon = "warning"
            icon_color = "orange"

        right = [
            Text("Place a drum to test", size="large", align="center"),
            Spacer(height=16),
            Center(children=[
                Row(children=[
                    StatusIcon(icon=icon, color=icon_color),
                    Column(children=[
                        StatusBadge(color_text, color=badge_color, glow=True),
                        Text(
                            f"Confidence: {self.confidence:.0%}"
                            if self.detected_color
                            else "No color detected",
                            size="small",
                            muted=True,
                        ),
                    ], spacing=4),
                ], align="center", spacing=12),
            ]),
            Spacer(height=16),
            Row(children=[
                Button("retry", "Retry", style="secondary"),
                Button("done", "Done", style="success"),
            ], align="center", spacing=12),
        ]

        return Split(
            left=[CamFeed(show_detections=True)],
            right=right,
            ratio=(3, 2),
        )

    @on_click("done")
    async def on_done(self):
        self.close("done")

    @on_click("retry")
    async def on_retry(self):
        self.close("retry")
