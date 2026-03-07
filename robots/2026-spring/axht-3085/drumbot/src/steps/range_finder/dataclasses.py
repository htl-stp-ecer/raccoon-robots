from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class RangeFinderCalibrationResult:
    confirmed: bool
    t_enter: float
    t_exit: float


@dataclass
class ScanData:
    samples: List[Tuple[float, float]]  # (heading_deg, value)
    baseline: float
    peak: float
    peak_heading_deg: float
