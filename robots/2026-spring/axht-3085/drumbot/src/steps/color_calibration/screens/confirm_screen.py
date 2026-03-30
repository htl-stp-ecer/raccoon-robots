from libstp.ui import *

from src.ui.widgets import CamFeed


class ColorConfirmScreen(UIScreen[bool]):
    """Split-screen: live feed (left) + calibrated ranges + confirm (right)."""

    _primary_button_id = "confirm"

    def __init__(
        self,
        blue_range: tuple[tuple[int, ...], tuple[int, ...]] | None,
        pink_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]] | None,
        min_area: int = 300,
    ):
        super().__init__()
        self.title = "Confirm Calibration"
        self.blue_range = blue_range
        self.pink_ranges = pink_ranges
        self.min_area = min_area

    def _fmt(self, lower: tuple[int, ...], upper: tuple[int, ...]) -> str:
        return f"H:{lower[0]}-{upper[0]}  S:{lower[1]}-{upper[1]}  V:{lower[2]}-{upper[2]}"

    def build(self) -> Widget:
        right = [
            Text("Calibrated Ranges", size="large", align="center", bold=True),
            Spacer(height=8),
        ]

        if self.blue_range:
            lo, hi = self.blue_range
            right.append(Card(title="Blue", children=[
                Text(self._fmt(lo, hi), size="medium"),
            ]))
        else:
            right.append(Card(title="Blue", children=[
                Text("Not calibrated (defaults)", size="medium", muted=True),
            ]))

        if self.pink_ranges:
            widgets = []
            for i, (lo, hi) in enumerate(self.pink_ranges):
                prefix = f"Range {i + 1}: " if len(self.pink_ranges) > 1 else ""
                widgets.append(Text(f"{prefix}{self._fmt(lo, hi)}", size="medium"))
            right.append(Card(title="Pink", children=widgets))
        else:
            right.append(Card(title="Pink", children=[
                Text("Not calibrated (defaults)", size="medium", muted=True),
            ]))

        right.append(Card(title="Noise Rejection", children=[
            Text(f"Min blob area: {self.min_area} px", size="medium"),
        ]))

        right.extend([
            Spacer(height=8),
            Row(children=[
                Button("retry", "Retry", style="secondary"),
                Button("confirm", "Save & Test", style="success"),
            ], align="center", spacing=12),
        ])

        return Split(
            left=[CamFeed()],
            right=right,
            ratio=(3, 2),
        )

    @on_click("confirm")
    async def on_confirm(self):
        self.close(True)

    @on_click("retry")
    async def on_retry(self):
        self.close(False)
