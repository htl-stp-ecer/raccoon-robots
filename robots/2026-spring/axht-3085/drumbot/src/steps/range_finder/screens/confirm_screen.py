from typing import List, Tuple

from libstp.ui import *

from ..dataclasses import RangeFinderCalibrationResult, ScanData


class RangeFinderConfirmScreen(UIScreen[RangeFinderCalibrationResult]):
    """Confirm T_enter / T_exit thresholds from scan results."""

    title = "Range Finder Calibration"

    def __init__(self, scan: ScanData, t_enter: float, t_exit: float):
        super().__init__()
        self.scan = scan
        self.t_enter = t_enter
        self.t_exit = t_exit

    @property
    def spread(self) -> float:
        return self.scan.peak - self.scan.baseline

    @property
    def is_good(self) -> bool:
        return (
            self.spread > 50
            and self.t_enter > self.t_exit
            and self.t_enter < self.scan.peak
        )

    def build(self) -> Widget:
        sensor_values = [v for _, v in self.scan.samples]
        return Split(
            left=[
                CalibrationChart(
                    samples=sensor_values,
                    thresholds=[
                        (self.t_enter, "T_enter", "orange"),
                        (self.t_exit, "T_exit", "blue"),
                    ],
                    height=200,
                ),
            ],
            right=[
                Row(children=[
                    StatusIcon(
                        icon="check" if self.is_good else "warning",
                        color="green" if self.is_good else "orange",
                    ),
                    Text(
                        "Scan Complete" if self.is_good else "Weak Signal",
                        size="large",
                    ),
                    Text(
                        f"Peak {self.scan.peak:.0f} at {self.scan.peak_heading_deg:.1f} deg"
                        f" | Spread {self.spread:.0f}",
                        size="small", muted=True,
                    ),
                ], align="center", spacing=6),
                Spacer(6),
                Row(children=[
                    Column(children=[
                        Text("T_enter", size="small", muted=True),
                        NumericInput(id="t_enter", value=self.t_enter),
                    ], spacing=2),
                    Column(children=[
                        Text("T_exit", size="small", muted=True),
                        NumericInput(id="t_exit", value=self.t_exit),
                    ], spacing=2),
                ], spacing=16),
                Spacer(6),
                Row(children=[
                    Button("retry", "Retry", style="secondary"),
                    Button("confirm", "Confirm",
                           style="success" if self.is_good else "warning"),
                ], spacing=8),
            ],
            ratio=(3, 2),
        )

    @on_change("t_enter")
    async def on_t_enter_change(self, value: float):
        self.t_enter = value
        await self.refresh()

    @on_change("t_exit")
    async def on_t_exit_change(self, value: float):
        self.t_exit = value
        await self.refresh()

    @on_click("retry")
    async def on_retry(self):
        self.close(RangeFinderCalibrationResult(
            confirmed=False,
            t_enter=self.t_enter,
            t_exit=self.t_exit,
        ))

    @on_click("confirm")
    async def on_confirm(self):
        self.close(RangeFinderCalibrationResult(
            confirmed=True,
            t_enter=self.t_enter,
            t_exit=self.t_exit,
        ))
