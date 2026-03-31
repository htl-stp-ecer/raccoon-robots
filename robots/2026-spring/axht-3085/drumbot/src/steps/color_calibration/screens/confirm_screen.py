from libstp.ui import *

from src.ui.widgets import CamFeed


class ColorConfirmScreen(UIScreen[str]):
    """Split-screen: live feed (left) + calibrated ranges + confirm (right).

    Closes with: "confirm", "retry_all", "retry_blue", or "retry_pink".
    """

    _primary_button_id = "confirm"

    def __init__(
        self,
        blue_range: tuple[tuple[int, ...], tuple[int, ...]] | None,
        blue_sat_min: int = 0,
        pink_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]] | None = None,
        pink_sat_min: int = 0,
        min_area: int = 300,
    ):
        super().__init__()
        self.title = "Confirm Calibration"
        self.blue_range = blue_range
        self.blue_sat_min = blue_sat_min
        self.pink_ranges = pink_ranges
        self.pink_sat_min = pink_sat_min
        self.min_area = min_area

    def _fmt_hsv(self, lower: tuple[int, ...], upper: tuple[int, ...]) -> str:
        return f"H:{lower[0]}-{upper[0]}  S:{lower[1]}-{upper[1]}  V:{lower[2]}-{upper[2]}"

    def _fmt_lab(self, lower: tuple[int, ...], upper: tuple[int, ...]) -> str:
        return f"L:{lower[0]}-{upper[0]}  a*:{lower[1]}-{upper[1]}  b*:{lower[2]}-{upper[2]}"

    def build(self) -> Widget:
        right = [
            Text("Calibrated Ranges", size="large", align="center", bold=True),
            Spacer(height=8),
        ]

        if self.blue_range:
            lo, hi = self.blue_range
            blue_children = [Text(self._fmt_lab(lo, hi), size="medium")]
            if self.blue_sat_min > 0:
                blue_children.append(Text(f"Sat gate: S >= {self.blue_sat_min}", size="small", muted=True))
            blue_children.append(Button("retry_blue", "Retry Blue", style="secondary"))
            right.append(Card(title="Blue (LAB)", children=blue_children))
        else:
            right.append(Card(title="Blue (LAB)", children=[
                Text("Not calibrated (defaults)", size="medium", muted=True),
                Button("retry_blue", "Retry Blue", style="secondary"),
            ]))

        if self.pink_ranges:
            widgets = []
            for i, (lo, hi) in enumerate(self.pink_ranges):
                prefix = f"Range {i + 1}: " if len(self.pink_ranges) > 1 else ""
                widgets.append(Text(f"{prefix}{self._fmt_lab(lo, hi)}", size="medium"))
            if self.pink_sat_min > 0:
                widgets.append(Text(f"Sat gate: S >= {self.pink_sat_min}", size="small", muted=True))
            widgets.append(Button("retry_pink", "Retry Pink", style="secondary"))
            right.append(Card(title="Pink (LAB)", children=widgets))
        else:
            right.append(Card(title="Pink (LAB)", children=[
                Text("Not calibrated (defaults)", size="medium", muted=True),
                Button("retry_pink", "Retry Pink", style="secondary"),
            ]))

        right.append(Card(title="Noise Rejection", children=[
            Text(f"Min blob area: {self.min_area} px", size="medium"),
        ]))

        right.extend([
            Spacer(height=8),
            Row(children=[
                Button("retry_all", "Retry All", style="secondary"),
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
        self.close("confirm")

    @on_click("retry_all")
    async def on_retry_all(self):
        self.close("retry_all")

    @on_click("retry_blue")
    async def on_retry_blue(self):
        self.close("retry_blue")

    @on_click("retry_pink")
    async def on_retry_pink(self):
        self.close("retry_pink")
