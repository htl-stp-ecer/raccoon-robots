from typing import List, Tuple

from libstp import GenericRobot, RobotService

from src.hardware.range_finder import RangeFinder


class RangeFinderService(RobotService):
    """Provides access to the ET range finder and threshold computation."""

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self._range_finder = RangeFinder(robot.defs.et_range_finder)

    @property
    def range_finder(self) -> RangeFinder:
        return self._range_finder

    @staticmethod
    def compute_thresholds(
        scan_data: List[Tuple[float, float]],
        enter_factor: float = 0.6,
        exit_factor: float = 0.4,
    ) -> Tuple[float, float]:
        """Determine T_enter and T_exit from scan data.

        Treats the lowest readings as baseline and computes thresholds as
        fractions of (peak - baseline).

        Returns:
            (t_enter, t_exit) -- T_enter > T_exit by design.
        """
        if not scan_data:
            raise ValueError("No scan data")
        values = [v for _, v in scan_data]
        baseline = min(values)
        peak = max(values)
        spread = peak - baseline
        t_enter = baseline + enter_factor * spread
        t_exit = baseline + exit_factor * spread
        return t_enter, t_exit
