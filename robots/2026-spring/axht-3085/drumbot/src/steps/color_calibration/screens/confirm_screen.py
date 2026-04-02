from libstp.ui import *

from src.ui.widgets import CamFeed


class ColorConfirmScreen(UIScreen[str]):
    """Split-screen: live feed (left) + calibrated sat threshold + confirm (right).

    Closes with: "confirm" or "retry_all".
    """

    _primary_button_id = "confirm"

    def __init__(self, sat_threshold: int, blue_sat: int, pink_sat: int, empty_sat: int):
        super().__init__()
        self.title = "Confirm Calibration"
        self.sat_threshold = sat_threshold
        self.blue_sat = blue_sat
        self.pink_sat = pink_sat
        self.empty_sat = empty_sat

    def build(self) -> Widget:
        margin = min(self.blue_sat, self.pink_sat) - self.sat_threshold
        empty_margin = self.sat_threshold - self.empty_sat

        right = [
            Text("Saturation Gate", size="large", align="center", bold=True),
            Spacer(height=8),
            Card(title="Captured Values", children=[
                Text(f"Blue drum:  S_max = {self.blue_sat}", size="medium"),
                Text(f"Pink drum:  S_max = {self.pink_sat}", size="medium"),
                Text(f"Empty:      S_max = {self.empty_sat}", size="medium"),
            ]),
            Card(title="Threshold", children=[
                Text(f"sat_threshold = {self.sat_threshold}", size="medium", bold=True),
                Text(f"Margin above empty: +{empty_margin}", size="small", muted=True),
                Text(f"Margin below drums: -{margin}", size="small", muted=True),
            ]),
            Spacer(height=8),
            Row(children=[
                Button("retry_all", "Retry", style="secondary"),
                Button("confirm", "Save & Test", style="success"),
            ], align="center", spacing=12),
        ]

        return Split(
            left=[CamFeed()],
            right=right,
            ratio=(3, 2),
        )

    @on_click("confirm")
    async def on_confirm(self):
        self.close("confirm")

    @on_click("retry_all")
    async def on_retry_all(self):
        self.close("retry_all")
