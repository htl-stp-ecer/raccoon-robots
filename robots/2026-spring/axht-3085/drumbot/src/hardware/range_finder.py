from libstp.sensor_et import ETSensor


EMA_ALPHA = 0.3  # smoothing factor for sensor readings (lower = smoother)


class RangeFinder:
    """Custom hardware wrapper for an ET analog range finder sensor.

    Wraps an ETSensor and holds calibratable T_enter / T_exit thresholds
    used by the peak-tracking turn algorithm.

    The ET sensor returns higher values when a reflective target is closer /
    more directly in its beam.  During a sweep the reading rises above T_enter
    when entering the target zone and falls below T_exit when leaving it.
    """

    def __init__(self, sensor: ETSensor):
        self._sensor = sensor
        self._t_enter: float | None = None
        self._t_exit: float | None = None
        self._filtered: float | None = None

    @property
    def port(self) -> int:
        return self._sensor.port

    @property
    def is_calibrated(self) -> bool:
        return self._t_enter is not None and self._t_exit is not None

    @property
    def t_enter(self) -> float | None:
        return self._t_enter

    @property
    def t_exit(self) -> float | None:
        return self._t_exit

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

    def apply_calibration(self, t_enter: float, t_exit: float) -> None:
        self._t_enter = t_enter
        self._t_exit = t_exit

    def is_above_enter(self, value: float) -> bool:
        assert self.is_calibrated, "RangeFinder not calibrated"
        return value >= self._t_enter

    def is_below_exit(self, value: float) -> bool:
        assert self.is_calibrated, "RangeFinder not calibrated"
        return value <= self._t_exit
