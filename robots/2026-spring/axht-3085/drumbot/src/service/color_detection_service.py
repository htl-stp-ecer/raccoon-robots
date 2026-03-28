
from libstp import GenericRobot, RobotService


class ColorDetectionService(RobotService):
    """Color detection — currently hardcoded, swap out for camera later."""

    HARDCODED_SEQUENCE: list[str] = [
        "blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink",
    ]

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self._index: int = 0

    async def detect_color(self) -> str:
        """Return 'blue' or 'pink' for the current drum.

        Replace this method body with camera logic when ready.
        """
        if self._index >= len(self.HARDCODED_SEQUENCE):
            raise RuntimeError(
                f"No more drums expected (index={self._index})",
            )
        color = self.HARDCODED_SEQUENCE[self._index]
        self._index += 1
        self.info(f"Detected color: {color} (drum #{self._index})")
        return color
