from raccoon.ui import *


class ColorConfirmScreen(UIScreen[str]):
    """Displays computed CIELAB chroma thresholds and lets the user confirm or retry.

    Closes with ``"confirm"`` to proceed or ``"retry_all"`` to redo captures.
    """

    _primary_button_id = "confirm"

    def __init__(
        self,
        chroma_threshold: int,
        blue_chroma: int,
        pink_chroma: int,
        empty_p95_chroma: int,
    ):
        super().__init__()
        self.title = "Calibration Results"
        self.chroma_threshold = chroma_threshold
        self.blue_chroma = blue_chroma
        self.pink_chroma = pink_chroma
        self.empty_p95_chroma = empty_p95_chroma

    def build(self) -> Widget:
        margin_above = self.chroma_threshold - self.empty_p95_chroma
        margin_below = min(self.blue_chroma, self.pink_chroma) - self.chroma_threshold
        ok = margin_above > 0 and margin_below > 0

        left = [
            Card(title="Chroma Samples", children=[
                ResultsTable(rows=[
                    ("Blue drum (p95 C*)", str(self.blue_chroma), None),
                    ("Pink drum (p95 C*)", str(self.pink_chroma), None),
                    ("Empty (p95 C*)", str(self.empty_p95_chroma), None),
                    ("Threshold", str(self.chroma_threshold), "success" if ok else "error"),
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
