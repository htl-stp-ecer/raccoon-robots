from dataclasses import dataclass

MIN_DELTA = 750.0  # hard minimum IR delta — calibration is refused below this


@dataclass
class DrumCalibrationResult:
    confirmed: bool
    blocked_threshold: float
    pocket_threshold: float
