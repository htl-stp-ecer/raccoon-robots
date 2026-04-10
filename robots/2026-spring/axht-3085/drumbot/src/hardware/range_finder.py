from __future__ import annotations

from dataclasses import dataclass

from raccoon.sensor_et import ETSensor

EMA_ALPHA = 0.3  # smoothing factor for sensor readings (lower = smoother)

DEFAULT_PROFILE = "default"


@dataclass
class CalibrationProfile:
    t_enter: float
    t_exit: float


class RangeFinder:
    """Custom hardware wrapper for an ET analog range finder sensor.

    Wraps an ETSensor and holds calibratable T_enter / T_exit thresholds
    used by the peak-tracking turn algorithm.

    Supports multiple named calibration profiles so the robot can be
    calibrated for different pipe positions and switch between them.

    The ET sensor returns higher values when a reflective target is closer /
    more directly in its beam.  During a sweep the reading rises above T_enter
    when entering the target zone and falls below T_exit when leaving it.
    """

    def __init__(self, sensor: ETSensor):
        self._sensor = sensor
        self._profiles: dict[str, CalibrationProfile] = {}
        self._active: str | None = None
        self._filtered: float | None = None

    @property
    def port(self) -> int:
        return self._sensor.port

    @property
    def is_calibrated(self) -> bool:
        return self._active is not None and self._active in self._profiles

    @property
    def active_profile(self) -> str | None:
        return self._active

    @property
    def t_enter(self) -> float | None:
        p = self._profiles.get(self._active) if self._active else None
        return p.t_enter if p else None

    @property
    def t_exit(self) -> float | None:
        p = self._profiles.get(self._active) if self._active else None
        return p.t_exit if p else None

    def read_raw(self) -> float:
        return float(self._sensor.read())

    def read_filtered(self) -> float:
        raw = self.read_raw()
        if self._filtered is None:
            self._filtered = raw
        else:
            self._filtered += EMA_ALPHA * (raw - self._filtered)
        return self._filtered

    def reset_filter(self) -> None:
        self._filtered = None

    def apply_calibration(
        self, t_enter: float, t_exit: float, profile: str = DEFAULT_PROFILE,
    ) -> None:
        self._profiles[profile] = CalibrationProfile(t_enter, t_exit)
        self._active = profile

    def load_profile(self, profile: str) -> None:
        if profile not in self._profiles:
            raise KeyError(
                f"No calibration profile '{profile}'. "
                f"Available: {list(self._profiles.keys())}"
            )
        self._active = profile

    def is_above_enter(self, value: float) -> bool:
        assert self.is_calibrated, "RangeFinder not calibrated"
        return value >= self._profiles[self._active].t_enter

    def is_below_exit(self, value: float) -> bool:
        assert self.is_calibrated, "RangeFinder not calibrated"
        return value <= self._profiles[self._active].t_exit
