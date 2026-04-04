import asyncio
import time
from collections import deque

from libstp import AnalogSensor, GenericRobot, Motor, RobotService

from .drum_motor_calibration_mixin import (
    DrumMotorCalibrationMixin,
    FULL_VELOCITY,
    SAMPLE_INTERVAL,
)

NUM_POCKETS = 9
CREEP_VELOCITY = 500   # creep speed for precise edge measurement
STALL_RETRIES = 3      # back-up-and-retry attempts before giving up
STALL_WINDOW = 0.2     # rolling window for stall detection (seconds)
STALL_MIN_NET_TICKS = 400  # minimum net ticks in commanded direction over the window
                           # BEMF when stuck goes in the wrong direction → net < 0 → instant fail


class MotorStalledError(Exception):
    """Raised when the drum motor encoder stops making progress."""
    pass


class DrumMotorService(DrumMotorCalibrationMixin, RobotService):
    """Drum motor: calibrate black/white, move by pockets."""

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self._init_calibration()
        self._current_pocket: int = 0
        self._at_midpoint: bool = False  # True when offset +half pocket from stripe
        self.collection_failed: bool = False

    @property
    def motor(self) -> Motor:
        return self.robot.defs.drum_motor

    @property
    def light_sensor(self) -> AnalogSensor:
        return self.robot.defs.drum_light_sensor

    # ── position tracking ────────────────────────────────────────

    @property
    def current_pocket(self) -> int:
        return self._current_pocket

    def reset_position(self, pocket: int = 0) -> None:
        self.info(f"Reset: pocket {self._current_pocket} → {pocket}")
        self._current_pocket = pocket

    # ── stall detection ──────────────────────────────────────────

    def _make_stall_checker(self, direction: int = 1) -> callable:
        """Return a callable that raises MotorStalledError if the motor isn't making progress.

        Uses a rolling STALL_WINDOW-second window of (time, position) samples.
        Net displacement = (newest - oldest) * direction.
        - BEMF when stuck goes in the wrong direction → net is negative → immediate fail.
        - BEMF noise that happens to go the right way but is tiny → net < threshold → fail.
        Only evaluates once the window is at least 90% full to avoid false triggers at startup.
        """
        history: deque = deque()  # (monotonic_time, encoder_position)

        def check():
            now = time.monotonic()
            pos = self.motor.get_position()
            history.append((now, pos))
            while history and now - history[0][0] > STALL_WINDOW:
                history.popleft()
            oldest_time, oldest_pos = history[0]
            if now - oldest_time < STALL_WINDOW * 0.9:
                return  # window not full yet — too early to judge
            net = (pos - oldest_pos) * direction
            if net < STALL_MIN_NET_TICKS:
                raise MotorStalledError(
                    f"Motor stalled — {net} net ticks in {now - oldest_time:.2f}s "
                    f"(need {STALL_MIN_NET_TICKS}, direction={direction:+d})"
                )

        return check

    async def _retry_on_stall(self, coro_fn, backup_sign: int) -> None:
        """Run coro_fn() with stall-retry: backs up and retries up to STALL_RETRIES times."""
        for attempt in range(1, STALL_RETRIES + 1):
            try:
                await coro_fn()
                return
            except MotorStalledError:
                self.motor.set_velocity(0)
                if attempt >= STALL_RETRIES:
                    self.warn(f"Motor stalled after {STALL_RETRIES} retries — giving up")
                    raise
                self.warn(f"Motor stalled (attempt {attempt}/{STALL_RETRIES}) — backing up to retry")
                self.motor.set_velocity(int(FULL_VELOCITY * 0.7) * backup_sign)
                await asyncio.sleep(0.30)
                self.motor.set_velocity(0)
                await asyncio.sleep(0.05)

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

    async def eject(self, pockets: int = 1) -> None:
        self.info(f"eject({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=False, velocity=int(FULL_VELOCITY * 0.8))

    async def eject_sweep(self, pockets: int, *, forward: bool = False) -> None:
        """Sweep N pockets at 70% speed using raw encoder ticks.

        Bypasses stripe counting and stall detection intentionally — this must be
        one uninterrupted motion so all drums clear the eject point cleanly.
        """
        assert self.is_calibrated
        await self._move(pockets, forward=forward, precise=False, velocity=int(FULL_VELOCITY * 0.7))

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

    async def _move(self, pockets: int, *, forward: bool, precise: bool = True, velocity: int = FULL_VELOCITY) -> None:
        """Move N pockets with stall detection and automatic retry."""
        backup_sign = -1 if forward else 1
        await self._retry_on_stall(
            lambda: self._do_move(pockets, forward=forward, precise=precise, velocity=velocity),
            backup_sign=backup_sign,
        )

    async def _do_move(self, pockets: int, *, forward: bool, precise: bool = True, velocity: int = FULL_VELOCITY) -> None:
        """Move N pockets counting stripe transitions."""
        assert self._ticks_per_pocket is not None, "Calibrate first (need ticks_per_pocket)"
        assert 0 < pockets < NUM_POCKETS, f"pockets must be 1..{NUM_POCKETS - 1}"
        sign = 1 if forward else -1
        tpp = self._ticks_per_pocket
        stall_check = self._make_stall_checker(direction=sign)

        self.info(f"{'fwd' if forward else 'bwd'} {pockets} pockets {'precise' if precise else 'fast'} (midpoint={self._at_midpoint})")

        stripes_to_count = pockets
        if self._at_midpoint and forward:
            stripes_to_count -= 1

        start_pos = self.motor.get_position()
        self.motor.set_velocity(velocity * sign)

        if self._at_midpoint:
            while abs(self.motor.get_position() - start_pos) < tpp // 2:
                stall_check()
                await asyncio.sleep(SAMPLE_INTERVAL)

        if stripes_to_count > 0:
            skip_start = self.motor.get_position()
            while abs(self.motor.get_position() - skip_start) < tpp // 3:
                stall_check()
                await asyncio.sleep(SAMPLE_INTERVAL)

            on_black = self._is_black()
            stripes_counted = 0
            entry_pos = 0

            while stripes_counted < stripes_to_count:
                stall_check()
                reading = self._is_black()
                if reading and not on_black:
                    stripes_counted += 1
                    entry_pos = self.motor.get_position()
                on_black = reading
                await asyncio.sleep(SAMPLE_INTERVAL)

        self.motor.set_velocity(0)

        if precise:
            await self._center_on_stripe(entry_pos)

        self._at_midpoint = False
        if forward:
            self._current_pocket = (self._current_pocket + pockets) % NUM_POCKETS
        else:
            self._current_pocket = (self._current_pocket - pockets) % NUM_POCKETS
        self.info(f"Move done: pocket={self._current_pocket}")

    async def _center_on_stripe(self, entry_pos: int) -> None:
        """Creep back and forth to find the center of the current stripe."""
        self.motor.move_to_position(FULL_VELOCITY, entry_pos)
        while not self.motor.is_done():
            await asyncio.sleep(SAMPLE_INTERVAL)

        self.motor.set_velocity(-CREEP_VELOCITY)
        while self._is_black():
            await asyncio.sleep(SAMPLE_INTERVAL)
        self.motor.set_velocity(0)

        self.motor.set_velocity(CREEP_VELOCITY)
        while not self._is_black():
            await asyncio.sleep(SAMPLE_INTERVAL)
        edge1 = self.motor.get_position()
        while self._is_black():
            await asyncio.sleep(SAMPLE_INTERVAL)
        edge2 = self.motor.get_position()
        self.motor.set_velocity(0)

        self.motor.move_to_position(FULL_VELOCITY, (edge1 + edge2) // 2)
        while not self.motor.is_done():
            await asyncio.sleep(SAMPLE_INTERVAL)

    async def move_to_midpoint(self) -> None:
        """Move forward half a pocket with stall retry."""
        assert self._ticks_per_pocket is not None

        async def _do():
            ticks = self._ticks_per_pocket // 3
            stall_check = self._make_stall_checker(direction=1)
            start = self.motor.get_position()
            self.motor.set_velocity(FULL_VELOCITY)
            while abs(self.motor.get_position() - start) < ticks:
                stall_check()
                await asyncio.sleep(SAMPLE_INTERVAL)
            self.motor.set_velocity(0)

        await self._retry_on_stall(_do, backup_sign=-1)
        self._at_midpoint = True

    async def move_from_midpoint(self) -> None:
        """Move backward half a pocket with stall retry."""
        assert self._ticks_per_pocket is not None

        async def _do():
            ticks = self._ticks_per_pocket // 2
            stall_check = self._make_stall_checker(direction=-1)
            start = self.motor.get_position()
            self.motor.set_velocity(-FULL_VELOCITY)
            while abs(self.motor.get_position() - start) < ticks:
                stall_check()
                await asyncio.sleep(SAMPLE_INTERVAL)
            self.motor.set_velocity(0)

        await self._retry_on_stall(_do, backup_sign=1)
        self._at_midpoint = False
