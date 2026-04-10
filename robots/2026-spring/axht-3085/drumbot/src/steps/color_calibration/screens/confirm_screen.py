from raccoon.ui import *


class ColorConfirmScreen(UIScreen[str]):
    """Displays computed saturation thresholds and lets the user confirm or retry.

    Closes with ``"confirm"`` to proceed or ``"retry_all"`` to redo captures.
    """

    _primary_button_id = "confirm"

    def __init__(
        self,
        sat_threshold: int,
        blue_sat: int,
        pink_sat: int,
        empty_sat: int,
    ):
        super().__init__()
        self.title = "Calibration Results"
        self.sat_threshold = sat_threshold
        self.blue_sat = blue_sat
        self.pink_sat = pink_sat
        self.empty_sat = empty_sat

    def build(self) -> Widget:
        margin_above = self.sat_threshold - self.empty_sat
        margin_below = min(self.blue_sat, self.pink_sat) - self.sat_threshold
        ok = margin_above > 0 and margin_below > 0

        left = [
            Card(title="Saturation Samples", children=[
                ResultsTable(rows=[
                    ("Blue drum", str(self.blue_sat), None),
                    ("Pink drum", str(self.pink_sat), None),
                    ("Empty", str(self.empty_sat), None),
                    ("Threshold", str(self.sat_threshold), "success" if ok else "error"),
                ]),
            ]),
        ]

        right = [
            Text("Calibration Results", size="large", align="center"),
            Spacer(height=12),
            HintBox(
                f"+{margin_above} above empty  |  -{margin_below} below drums"
                if ok else
                "Threshold too close to background — consider better lighting.",
                icon="check_circle" if ok else "warning",
            ),
            Spacer(height=16),
            Row(children=[
                Button("retry_all", "Retry All", style="secondary"),
                Button("confirm", "Confirm & Test", style="success"),
            ], align="center", spacing=12),
        ]

        return Split(left=left, right=right, ratio=(1, 1))

    @on_click("confirm")
    async def on_confirm(self):
        self.close("confirm")

    @on_click("retry_all")
    async def on_retry_all(self):
        self.close("retry_all")
