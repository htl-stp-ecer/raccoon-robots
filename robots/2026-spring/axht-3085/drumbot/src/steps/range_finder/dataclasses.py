from dataclasses import dataclass


@dataclass
class RangeFinderCalibrationResult:
    confirmed: bool
    t_enter: float
    t_exit: float


@dataclass
class ScanData:
    samples: list[tuple[float, float]]  # (heading_deg, value)
    baseline: float
    peak: float
    peak_heading_deg: float
