import asyncio

from libstp import AnalogSensor, GenericRobot, IRSensor, KMeans, Motor, RobotService

NUM_POCKETS = 9
SAMPLE_INTERVAL = 0.01  # ~100 Hz
HYSTERESIS_FRACTION = 0.15
FULL_VELOCITY = 1700  # max velocity for set_velocity / move_to_position
CREEP_VELOCITY = 500  # creep speed for precise edge measurement


class DrumMotorService(RobotService):
    """Drum motor: calibrate black/white, move by pockets."""

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self._blocked_threshold: float | None = None
        self._pocket_threshold: float | None = None
        self._ticks_per_pocket: int | None = None
        self._current_pocket: int = 0
        self._at_midpoint: bool = False  # True when offset +half pocket from stripe
        self.collection_failed: bool = False

    @property
    def motor(self) -> Motor:
        return self.robot.defs.drum_motor

    @property
    def light_sensor(self) -> AnalogSensor:
        return self.robot.defs.drum_light_sensor

    # ── calibration ──────────────────────────────────────────────

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

    async def sample(self, duration: float, motor_speed: float = 1.0) -> list[float]:
        """Spin motor, collect light sensor readings with encoder positions."""
        self.info(f"Sampling: duration={duration}s, motor_speed={motor_speed}")
        samples: list[float] = []
        self._sample_positions: list[int] = []
        velocity = int(motor_speed * FULL_VELOCITY)
        start_encoder = self.motor.get_position()
        self.motor.set_velocity(velocity)
        try:
            loop = asyncio.get_event_loop()
            t_end = loop.time() + duration
            while loop.time() < t_end:
                samples.append(float(self.light_sensor.read()))
                self._sample_positions.append(self.motor.get_position())
                await asyncio.sleep(SAMPLE_INTERVAL)
        finally:
            self.motor.set_velocity(0)
        end_encoder = self.motor.get_position()
        self._sample_total_ticks = abs(end_encoder - start_encoder)
        if samples:
            self.info(f"Collected {len(samples)} samples — min={min(samples):.0f}, max={max(samples):.0f}, avg={sum(samples)/len(samples):.0f}, ticks={self._sample_total_ticks}")
        return samples

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
        """Read sensor and return True if on a black pocket (using high threshold)."""
        _, high = self.hysteresis_thresholds
        return float(self.light_sensor.read()) >= high

    def _is_white(self) -> bool:
        """Read sensor and return True if on white (using low threshold)."""
        low, _ = self.hysteresis_thresholds
        return float(self.light_sensor.read()) <= low

    # ── position tracking ────────────────────────────────────────

    @property
    def current_pocket(self) -> int:
        return self._current_pocket

    def reset_position(self, pocket: int = 0) -> None:
        self.info(f"Reset: pocket {self._current_pocket} → {pocket}")
        self._current_pocket = pocket

    # ── navigation ───────────────────────────────────────────────

    async def advance(self, pockets: int = 1, *, precise: bool = False) -> None:
        """Move forward N pockets (black stripes)."""
        self.info(f"advance({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=True, precise=precise)

    async def retreat(self, pockets: int = 1, *, precise: bool = False) -> None:
        """Move backward N pockets."""
        self.info(f"retreat({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=False, precise=precise)

    async def reject(self, pockets: int = 1) -> None:
        self.info(f"reject({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=False)

    async def go_to_pocket(self, pocket: int, *, precise: bool = False) -> str:
        delta = (pocket - self._current_pocket) % NUM_POCKETS
        if delta == 0:
            self.info(f"Already at pocket {pocket}")
            return "none"
        if delta <= NUM_POCKETS // 2:
            await self.advance(delta, precise=precise)
            return "forward"
        else:
            await self.retreat(NUM_POCKETS - delta, precise=precise)
            return "backward"

    async def go_to_edge(self, target_edge: int) -> str:
        """Compat: convert edge to pocket and go there."""
        return await self.go_to_pocket(target_edge // 2)

    async def _move(self, pockets: int, *, forward: bool, precise: bool = True) -> None:
        """Move N pockets at full velocity, counting stripe transitions.

        Runs at FULL_VELOCITY, polls sensor to count black stripes using
        encoder skip to avoid re-detecting the starting stripe.

        precise=False: stops immediately when last stripe detected (fast,
        may overshoot slightly — fine for non-critical positioning).
        precise=True: after detecting last stripe, returns to entry position
        and creeps across stripe to find center (direction-independent).
        """
        assert self._ticks_per_pocket is not None, "Calibrate first (need ticks_per_pocket)"
        assert 0 < pockets < NUM_POCKETS, f"pockets must be 1..{NUM_POCKETS - 1}"
        sign = 1 if forward else -1
        tpp = self._ticks_per_pocket
        skip_ticks = tpp // 3

        direction = "fwd" if forward else "bwd"
        self.info(f"{direction} {pockets} pockets {'precise' if precise else 'fast'} (midpoint={self._at_midpoint})")

        start_pos = self.motor.get_position()
        self.motor.set_velocity(FULL_VELOCITY * sign)

        # If at midpoint, clear the extra half-pocket first
        if self._at_midpoint:
            while abs(self.motor.get_position() - start_pos) < tpp // 2:
                await asyncio.sleep(SAMPLE_INTERVAL)

        # Skip past current stripe
        skip_start = self.motor.get_position()
        while abs(self.motor.get_position() - skip_start) < skip_ticks:
            await asyncio.sleep(SAMPLE_INTERVAL)

        # Count stripe transitions at full speed
        on_black = self._is_black()
        stripes_counted = 0
        entry_pos = 0

        while stripes_counted < pockets:
            reading = self._is_black()
            if reading and not on_black:
                stripes_counted += 1
                entry_pos = self.motor.get_position()
            on_black = reading
            await asyncio.sleep(SAMPLE_INTERVAL)

        # Stop
        self.motor.set_velocity(0)

        if precise:
            # Return to entry, then creep to find stripe center
            self.motor.move_to_position(FULL_VELOCITY, entry_pos)
            while not self.motor.is_done():
                await asyncio.sleep(SAMPLE_INTERVAL)

            # Creep backward off stripe
            self.motor.set_velocity(-CREEP_VELOCITY)
            while self._is_black():
                await asyncio.sleep(SAMPLE_INTERVAL)
            self.motor.set_velocity(0)

            # Creep forward across stripe to find both edges
            self.motor.set_velocity(CREEP_VELOCITY)
            while not self._is_black():
                await asyncio.sleep(SAMPLE_INTERVAL)
            edge1 = self.motor.get_position()
            while self._is_black():
                await asyncio.sleep(SAMPLE_INTERVAL)
            edge2 = self.motor.get_position()
            self.motor.set_velocity(0)

            center = (edge1 + edge2) // 2
            self.motor.move_to_position(FULL_VELOCITY, center)
            while not self.motor.is_done():
                await asyncio.sleep(SAMPLE_INTERVAL)

        self._at_midpoint = False
        if forward:
            self._current_pocket = (self._current_pocket + pockets) % NUM_POCKETS
        else:
            self._current_pocket = (self._current_pocket - pockets) % NUM_POCKETS

        self.info(f"Move done: pocket={self._current_pocket}")

    async def move_to_midpoint(self) -> None:
        """Move forward half a pocket using set_velocity (no PID settle)."""
        assert self._ticks_per_pocket is not None
        ticks = self._ticks_per_pocket // 2
        start = self.motor.get_position()
        self.motor.set_velocity(FULL_VELOCITY)
        while abs(self.motor.get_position() - start) < ticks:
            await asyncio.sleep(SAMPLE_INTERVAL)
        self.motor.set_velocity(0)
        self._at_midpoint = True

    async def move_from_midpoint(self) -> None:
        """Move backward half a pocket using set_velocity (no PID settle)."""
        assert self._ticks_per_pocket is not None
        ticks = self._ticks_per_pocket // 2
        start = self.motor.get_position()
        self.motor.set_velocity(-FULL_VELOCITY)
        while abs(self.motor.get_position() - start) < ticks:
            await asyncio.sleep(SAMPLE_INTERVAL)
        self.motor.set_velocity(0)
        self._at_midpoint = False
