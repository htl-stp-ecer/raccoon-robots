import time

from raccoon.ui.screen import UIScreen
from raccoon.ui.widgets import Center, Column, Container, Row, Spacer, StatusBadge, Text, Widget

MISS_FLASH_COLOR = "#C62828"
MISS_FLASH_DURATION = 5.0  # seconds the background stays red after a detection miss


class DrumCollectionScreen(UIScreen[None]):
    """Live display of detected color + countdown to next drum."""

    title = "Drum Collection"

    def __init__(self):
        super().__init__()
        self.detected_color: str | None = None
        self.drum_number: int = 0
        self.total_drums: int = 8
        self.countdown: float = 0.0
        self.status: str = "Waiting..."
        self._miss_flash_until: float = 0.0  # time.monotonic() deadline

    def flag_miss(self, duration: float = MISS_FLASH_DURATION) -> None:
        """Flash the background red for ``duration`` seconds (a drum was expected but not detected)."""
        self._miss_flash_until = time.monotonic() + duration

    def build(self) -> Widget:
        color_text = self.detected_color or "—"
        badge_color = {
            "blue": "blue",
            "pink": "red",
        }.get(self.detected_color or "", "grey")

        content = Column(children=[
            Text(
                f"Drum {self.drum_number}/{self.total_drums}",
                size="title", bold=True, align="center",
            ),
            Spacer(height=12),
            Row(children=[
                Text("Detected: ", size="large", align="right"),
                StatusBadge(
                    text=color_text.upper(),
                    color=badge_color,
                    glow=self.detected_color is not None,
                ),
            ]),
            Spacer(height=12),
            Text(
                f"Next in: {self.countdown:.1f}s" if self.countdown > 0 else self.status,
                size="large",
                align="center",
                color="#FFD700" if self.countdown > 0 else None,
            ),
        ])

        flashing = time.monotonic() < self._miss_flash_until
        return Container(
            bg_color=MISS_FLASH_COLOR if flashing else None,
            children=[Center(children=[content])],
        )
