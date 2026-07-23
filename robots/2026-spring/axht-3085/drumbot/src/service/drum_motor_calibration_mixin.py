import asyncio

from raccoon import AnalogSensor, IRSensor, KMeans, Motor

HYSTERESIS_FRACTION = 0.15
FULL_VELOCITY = 1700   # max velocity for set_velocity / move_to_position
SAMPLE_INTERVAL = 0.01  # ~100 Hz


class DrumMotorCalibrationMixin:
    """Calibration state and methods for DrumMotorService.

    Expects the host class to provide:
      - self.motor: Motor
      - self.light_sensor: AnalogSensor
      - self.info(msg), self.warn(msg)
    """

    def _init_calibration(self) -> None:
        self._blocked_threshold: float | None = None
        self._pocket_threshold: float | None = None
        self._ticks_per_pocket: int | None = None

    # ── calibration state ────────────────────────────────────────

    @property
    def is_calibrated(self) -> bool:
        return self._blocked_threshold is not None and self._pocket_threshold is not None

    @property
    def midpoint(self) -> float:
        assert self.is_calibrated
        return (self._blocked_threshold + self._pocket_threshold) / 2

    @property
    def hysteresis_thresholds(self) -> tuple[float, float]:
        assert self.is_calibrated
        mid = self.midpoint
        band = (self._blocked_threshold - self._pocket_threshold) * HYSTERESIS_FRACTION
        return (mid - band, mid + band)

    @property
    def blocked_threshold(self) -> float | None:
        return self._blocked_threshold

    @property
    def pocket_threshold(self) -> float | None:
        return self._pocket_threshold

    # ── sampling ─────────────────────────────────────────────────

    async def sample(self, duration: float, motor_speed: float = 1.0) -> list[float]:
        """Spin motor, collect light sensor readings with encoder positions."""
        self.info(f"Sampling: duration={duration}s, motor_speed={motor_speed}")
        samples: list[float] = []
        self._sample_positions: list[int] = []
        # Open-loop PWM, NOT set_velocity: the drum motor has no BEMF/static-
        # friction calibration, so the closed-loop velocity PID never overcomes
        # stiction and the drum won't turn. Sampling only needs a steady sweep
        # across the stripes, so raw set_speed is both sufficient and reliable.
        # TODO(drum-cal): verify on hardware (see DRUM_KALIBRIERUNG_FIX.md). The
        # navigation moves in drum_motor_service.py still use set_velocity — if the
        # drum also won't turn while sorting, tune drum_motor's MotorCalibration
        # (bemf_offset + static_friction_pct) or switch those moves to set_speed too.
        speed_pct = int(motor_speed * 100)
        start_encoder = self.motor.get_position()
        self.motor.set_speed(speed_pct)
        try:
            loop = asyncio.get_event_loop()
            t_end = loop.time() + duration
            while loop.time() < t_end:
                samples.append(float(self.light_sensor.read()))
                self._sample_positions.append(self.motor.get_position())
                await asyncio.sleep(SAMPLE_INTERVAL)
        finally:
            self.motor.set_speed(0)
        end_encoder = self.motor.get_position()
        self._sample_total_ticks = abs(end_encoder - start_encoder)
        if samples:
            self.info(
                f"Collected {len(samples)} samples — "
                f"min={min(samples):.0f}, max={max(samples):.0f}, "
                f"avg={sum(samples)/len(samples):.0f}, ticks={self._sample_total_ticks}"
            )
        return samples

    # ── analysis helpers ─────────────────────────────────────────

    def cluster(self, samples: list[float]) -> tuple[float, float]:
        """Run 2-means clustering. Returns (pocket, blocked) centroids."""
        km = KMeans(max_iterations=10)
        result = km.fit(samples)
        pocket = min(result.centroid1, result.centroid2)
        blocked = max(result.centroid1, result.centroid2)
        self.info(f"Cluster: pocket={pocket:.0f}, blocked={blocked:.0f}, spread={blocked - pocket:.0f}")
        return pocket, blocked

    def analyse_stripe_spacing(
        self,
        samples: list[float],
        blocked: float,
        pocket: float,
    ) -> tuple[int, list[int], list[int]]:
        """Find stripe transitions in sample data, return (count, spacings, encoder_positions)."""
        mid = (blocked + pocket) / 2
        band = (blocked - pocket) * HYSTERESIS_FRACTION
        s_low, s_high = mid - band, mid + band

        on_black = False
        stripe_positions: list[int] = []
        positions = getattr(self, "_sample_positions", [])

        for i, val in enumerate(samples):
            if not on_black and val >= s_high:
                on_black = True
                if i < len(positions):
                    stripe_positions.append(positions[i])
            elif on_black and val <= s_low:
                on_black = False

        spacings = [
            abs(stripe_positions[i + 1] - stripe_positions[i])
            for i in range(len(stripe_positions) - 1)
        ]
        return len(stripe_positions), spacings, stripe_positions

    def check_spacing_uniformity(
        self, spacings: list[int], tolerance: float = 0.35
    ) -> tuple[bool, float]:
        """Check that stripe spacings are uniform within *tolerance* fraction."""
        if len(spacings) < 2:
            return False, 1.0
        median = sorted(spacings)[len(spacings) // 2]
        if median == 0:
            return False, 1.0
        max_dev = max(abs(s - median) / median for s in spacings)
        return max_dev <= tolerance, max_dev

    def apply_calibration(
        self,
        blocked: float,
        pocket: float,
        samples: list[float] | None = None,
        ticks_per_pocket: int | None = None,
    ) -> None:
        self._blocked_threshold = blocked
        self._pocket_threshold = pocket
        if isinstance(self.light_sensor, IRSensor):
            self.light_sensor.setCalibration(blocked, pocket)
        low, high = self.hysteresis_thresholds

        if ticks_per_pocket is not None:
            self._ticks_per_pocket = ticks_per_pocket
            self.info(f"Ticks per pocket (stored): {self._ticks_per_pocket}")
        elif samples is not None and hasattr(self, "_sample_total_ticks"):
            stripe_count, spacings, _ = self.analyse_stripe_spacing(samples, blocked, pocket)
            if stripe_count > 0:
                if spacings:
                    self._ticks_per_pocket = sorted(spacings)[len(spacings) // 2]
                else:
                    self._ticks_per_pocket = self._sample_total_ticks // stripe_count
                self.info(f"Ticks per pocket: {self._ticks_per_pocket} ({stripe_count} stripes, spacings={spacings})")
                ok, dev = self.check_spacing_uniformity(spacings)
                if ok:
                    self.info(f"Spacing uniformity OK (max deviation {dev:.1%})")
                else:
                    self.warn(f"Spacing NOT uniform (max deviation {dev:.1%}) — may need longer sampling")

        self.info(f"Calibration: pocket={pocket:.0f}, blocked={blocked:.0f}, hysteresis=[{low:.0f}, {high:.0f}]")

    # ── sensor helpers ───────────────────────────────────────────

    def _is_black(self) -> bool:
        _, high = self.hysteresis_thresholds
        return float(self.light_sensor.read()) >= high

    def _is_black_from_raw(self, raw: float) -> bool:
        """Like _is_black() but uses an already-read raw value (avoids double reads)."""
        _, high = self.hysteresis_thresholds
        return raw >= high

    def _is_white(self) -> bool:
        low, _ = self.hysteresis_thresholds
        return float(self.light_sensor.read()) <= low
