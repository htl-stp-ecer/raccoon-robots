import asyncio

from libstp import AnalogSensor, GenericRobot, IRSensor, KMeans, Motor, RobotService

NUM_POCKETS = 9
SAMPLE_INTERVAL = 0.01  # ~100 Hz
HYSTERESIS_FRACTION = 0.15
FULL_SPEED = 1.0
CREEP_SPEED = 0.15  # slow speed for precise edge detection
PID_SETTLE_SPEED = 1500  # velocity arg for move_to_position PID settle


class DrumMotorService(RobotService):
    """Drum motor: calibrate black/white, move by pockets."""

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self._blocked_threshold: float | None = None
        self._pocket_threshold: float | None = None
        self._ticks_per_pocket: int | None = None
        self._current_pocket: int = 0
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

    async def sample(self, duration: float, motor_speed: float = FULL_SPEED) -> list[float]:
        """Spin motor, collect light sensor readings with encoder positions."""
        self.info(f"Sampling: duration={duration}s, motor_speed={motor_speed}")
        samples: list[float] = []
        self._sample_positions: list[int] = []
        speed_percent = int(motor_speed * 100)
        start_encoder = self.motor.get_position()
        self.motor.set_speed(speed_percent)
        try:
            loop = asyncio.get_event_loop()
            t_end = loop.time() + duration
            while loop.time() < t_end:
                samples.append(float(self.light_sensor.read()))
                self._sample_positions.append(self.motor.get_position())
                await asyncio.sleep(SAMPLE_INTERVAL)
        finally:
            self.motor.set_speed(0)
            self.motor.brake()
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

    async def advance(self, pockets: int = 1) -> None:
        """Move forward N pockets (black stripes)."""
        self.info(f"advance({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=True)

    async def retreat(self, pockets: int = 1) -> None:
        """Move backward N pockets."""
        self.info(f"retreat({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=False)

    async def reject(self, pockets: int = 1) -> None:
        self.info(f"reject({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=False)

    async def go_to_pocket(self, pocket: int) -> str:
        delta = (pocket - self._current_pocket) % NUM_POCKETS
        if delta == 0:
            self.info(f"Already at pocket {pocket}")
            return "none"
        if delta <= NUM_POCKETS // 2:
            await self.advance(delta)
            return "forward"
        else:
            await self.retreat(NUM_POCKETS - delta)
            return "backward"

    async def go_to_edge(self, target_edge: int) -> str:
        """Compat: convert edge to pocket and go there."""
        return await self.go_to_pocket(target_edge // 2)

    def _ramp_speed(self, traveled: int, total: int, sign: int) -> int:
        """Linear decel ramp from FULL_SPEED to CREEP_SPEED over the pocket distance.

        Returns signed speed percent (min CREEP_SPEED).
        """
        fraction = min(traveled / total, 1.0)
        speed = FULL_SPEED - fraction * (FULL_SPEED - CREEP_SPEED)
        return max(int(speed * 100), int(CREEP_SPEED * 100)) * sign

    async def _move(self, pockets: int, *, forward: bool) -> None:
        """Move N pockets by polling the sensor directly.

        Each pocket transition: skip past current stripe by encoder distance,
        wait for white, wait for black.  On the last pocket a linear decel ramp
        brings us to creep speed by the time we reach the stripe, then we creep
        across it to measure both edges and settle on the center.
        """
        assert self._ticks_per_pocket is not None, "Calibrate first (need ticks_per_pocket)"
        assert 0 < pockets < NUM_POCKETS, f"pockets must be 1..{NUM_POCKETS - 1}"
        sign = 1 if forward else -1
        full = int(FULL_SPEED * 100) * sign
        skip_ticks = self._ticks_per_pocket // 2
        tpp = self._ticks_per_pocket
        direction = "fwd" if forward else "bwd"

        self.info(f"{direction} {pockets} pockets, skip_ticks={skip_ticks}")

        for i in range(pockets):
            is_last = i == pockets - 1
            start_pos = self.motor.get_position()

            self.motor.set_speed(full)

            # Phase 1: skip past current stripe (encoder distance floor)
            while abs(self.motor.get_position() - start_pos) < skip_ticks:
                if is_last:
                    traveled = abs(self.motor.get_position() - start_pos)
                    self.motor.set_speed(self._ramp_speed(traveled, tpp, sign))
                await asyncio.sleep(SAMPLE_INTERVAL)

            # Phase 2: if still on black, wait for white (with ramp on last)
            while self._is_black():
                if is_last:
                    traveled = abs(self.motor.get_position() - start_pos)
                    self.motor.set_speed(self._ramp_speed(traveled, tpp, sign))
                await asyncio.sleep(SAMPLE_INTERVAL)

            # Phase 3: wait for black — on last pocket continue ramping down
            while not self._is_black():
                if is_last:
                    traveled = abs(self.motor.get_position() - start_pos)
                    self.motor.set_speed(self._ramp_speed(traveled, tpp, sign))
                await asyncio.sleep(SAMPLE_INTERVAL)

            entry_pos = self.motor.get_position()

            if forward:
                self._current_pocket = (self._current_pocket + 1) % NUM_POCKETS
            else:
                self._current_pocket = (self._current_pocket - 1) % NUM_POCKETS

            self.info(f"  pocket {i}: hit black at pos={entry_pos} (moved {abs(entry_pos - start_pos)}), pocket={self._current_pocket}, last={is_last}")

            if is_last:
                # Already at creep speed — cross the stripe to find exit edge
                creep = int(CREEP_SPEED * 100) * sign
                self.motor.set_speed(creep)
                while self._is_black():
                    await asyncio.sleep(SAMPLE_INTERVAL)
                exit_pos = self.motor.get_position()
                self.motor.set_speed(0)
                self.motor.brake()

                center_pos = (entry_pos + exit_pos) // 2
                self.info(f"  stripe: entry={entry_pos}, exit={exit_pos}, width={abs(exit_pos - entry_pos)}, center={center_pos}")

                self.motor.move_to_position(PID_SETTLE_SPEED, center_pos)
                while not self.motor.is_done():
                    await asyncio.sleep(SAMPLE_INTERVAL)
                self.motor.brake()
                final_pos = self.motor.get_position()
                self.info(f"  settled: target={center_pos}, actual={final_pos}, delta={abs(final_pos - center_pos)}")

        self.info(f"Move done: pocket={self._current_pocket}")

    async def move_to_midpoint(self) -> None:
        """Move forward half a pocket (to sit on the divider between two pockets)."""
        assert self._ticks_per_pocket is not None
        ticks = self._ticks_per_pocket // 2
        self.info(f"Moving to midpoint: +{ticks} ticks")
        target = self.motor.get_position() + ticks
        self.motor.move_to_position(PID_SETTLE_SPEED, target)
        while not self.motor.is_done():
            await asyncio.sleep(SAMPLE_INTERVAL)
        self.motor.brake()

    async def move_from_midpoint(self) -> None:
        """Move backward half a pocket (back to the pocket center)."""
        assert self._ticks_per_pocket is not None
        ticks = self._ticks_per_pocket // 2
        self.info(f"Moving from midpoint: -{ticks} ticks")
        target = self.motor.get_position() - ticks
        self.motor.move_to_position(PID_SETTLE_SPEED, target)
        while not self.motor.is_done():
            await asyncio.sleep(SAMPLE_INTERVAL)
        self.motor.brake()
