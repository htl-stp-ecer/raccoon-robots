from libstp.ui import *


class RangeFinderScanningScreen(UIScreen[None]):
    """Screen shown while the robot sweeps and scans the ET range finder."""

    title = "Range Finder Calibration"

    def __init__(self, sensor_port: int):
        super().__init__()
        self.sensor_port = sensor_port
        self.sample_count = 0

    def build(self) -> Widget:
        return Split(
            left=[
                Row(children=[
                    ProgressSpinner(size=24),
                    Spacer(8),
                    Text("Scanning...", size="large"),
                ], align="center"),
                Spacer(8),
                Text("Robot is sweeping to the right. Keep target at ~15 cm.", size="small", muted=True),
                Spacer(16),
                Text(f"{self.sample_count} samples", size="small", muted=True),
            ],
            right=[
                Card(title=f"ET Sensor (Port {self.sensor_port})", children=[
                    SensorValue(port=self.sensor_port, sensor_type="analog"),
                ]),
            ],
            ratio=(1, 1),
        )
