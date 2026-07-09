import asyncio
import time
from collections import deque

from raccoon import AnalogSensor, GenericRobot, Motor, RobotService

from .drum_motor_calibration_mixin import (
    DrumMotorCalibrationMixin,
    FULL_VELOCITY,
    SAMPLE_INTERVAL,
)

NUM_POCKETS = 8
CREEP_VELOCITY = 500   # creep speed for precise edge measurement
STALL_RETRIES = 3      # default total attempts before giving up (per-instance overridable via .stall_retries)
STALL_WINDOW = 0.2     # rolling window for stall detection (seconds)
STALL_MIN_NET_TICKS = 75  # minimum net ticks in commanded direction over the window
                           # BEMF when stuck goes in the wrong direction → net < 0 → instant fail
COAST_SETTLE_SECONDS = 0.20  # post-stop pause so the tracker can absorb any coast-through
DRIFT_CORRECTION_TIMEOUT = 1.5  # max seconds for a closed-loop coast-drift correction move


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
        # True only when an emergency was caused by a GENUINE motor stall
        # (MotorStalledError) — as opposed to a camera-stuck watchdog or a
        # timing-blown abort, where the motor is mechanically fine. Ejection
        # uses this to pick its retry budget (see begin_eject).
        self.motor_faulted: bool = False
        # True once we've entered the post-collection eject phase. While set,
        # motor_locked is bypassed so drums are still ejected even after an
        # emergency — the stall_retries budget (not a hard nav lock) is what
        # protects a faulted big drum.
        self.eject_mode: bool = False
        # Overridable per-call-site: collection runs with stricter retry budget;
        # ejection keeps the default to tolerate transient jams without killing.
        self.stall_retries: int = STALL_RETRIES
        # ── continuous IR stripe tracker ──
        # Background asyncio task that polls the drum light sensor and
        # updates _current_pocket on every real stripe crossing. The tracker
        # is the single source of truth for pocket position — _do_move
        # simply commands motion and waits for the index to reach target.
        self._tracker_task: asyncio.Task | None = None
        self._tracker_on_black: bool = False
        self._tracker_last_edge_pos: int = 0
        self._last_entry_pos: int = 0  # motor position of the most recent counted stripe
        self._move_start_pos: int | None = None  # set at start of each _do_move; gates early detection

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

    @property
    def at_midpoint(self) -> bool:
        return self._at_midpoint

    @property
    def motor_locked(self) -> bool:
        """True once an emergency / safe mode has been entered.

        Every emergency path sets ``collection_failed`` (stall, stuck-drum
        watchdog, timing-blown). Once that is set, all revolver navigation is
        suppressed so a faulted big drum is never driven again — protecting the
        hardware while the rest of the run (chassis, lift, pusher) continues.

        EXCEPTION: during the post-collection eject phase (``eject_mode``) we
        deliberately drop the lock so the drums are still ejected even after an
        emergency. A faulted drum is instead protected by the reduced
        ``stall_retries`` budget (one careful attempt, no retry) that
        ``begin_eject`` installs.
        """
        if self.eject_mode:
            return False
        return self.collection_failed

    def begin_eject(self) -> None:
        """Enter the eject phase: allow revolver nav even after an emergency.

        Retry budget is chosen by emergency cause:
          - genuine motor stall  → 1 attempt, no retry (one careful try; if it
            stalls again the caller brakes and moves on),
          - camera-stuck / timing / no emergency → normal budget, since the
            motor is mechanically fine.

        Idempotent: safe to call at the start of every eject step.
        """
        self.eject_mode = True
        if self.motor_faulted:
            self.stall_retries = 1
            self.warn(
                "Eject phase: motor previously faulted — single careful attempt, no retry"
            )
        else:
            self.stall_retries = STALL_RETRIES
            if self.collection_failed:
                self.info(
                    "Eject phase: emergency was non-motor (camera/timing) — "
                    "attempting eject with normal retry budget"
                )

    def reset_position(self, pocket: int = 0) -> None:
        self.info(f"Reset: pocket {self._current_pocket} → {pocket}")
        self._current_pocket = pocket
        self._tracker_last_edge_pos = self.motor.get_position()
        self._last_entry_pos = self._tracker_last_edge_pos

    # ── continuous IR stripe tracker ─────────────────────────────

    def start_position_tracking(self) -> None:
        """Spawn the background IR tracker. Call once after calibration."""
        if self._tracker_task is not None and not self._tracker_task.done():
            return
        assert self._ticks_per_pocket is not None, "Calibrate before starting tracker"
        self._tracker_on_black = self._is_black()
        self._tracker_last_edge_pos = self.motor.get_position()
        self._last_entry_pos = self._tracker_last_edge_pos
        self._tracker_task = asyncio.create_task(self._track_position_loop())
        self.info(
            f"IR tracker started "
            f"(on_black={self._tracker_on_black}, pos={self._tracker_last_edge_pos})"
        )

    async def stop_position_tracking(self) -> None:
        """Cancel the background tracker (for shutdown / test teardown)."""
        task = self._tracker_task
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._tracker_task = None
        self.info("IR tracker stopped")

    async def _track_position_loop(self) -> None:
        """Watch the IR sensor forever; update _current_pocket on every real crossing.

        A "real" crossing is a rising edge (white → black) whose motor
        position is at least half a pocket away from the previous
        counted edge. That filter swallows small oscillations from
        _center_on_stripe's creep without suppressing legitimate moves
        (stripes are one full pocket apart).

        Direction comes from the encoder delta between edges — not from
        the commanded velocity — so coast-through after stop is tracked
        the same as deliberate motion.
        """
        assert self._ticks_per_pocket is not None
        # Gate 1 (idle only): prevents a false count from tiny motor drift back into
        # a stripe it just coasted past. Set to 15% — enough to swallow sub-1%
        # drift (observed: 227 ticks = 0.17%) while still allowing genuine
        # coast-through counts when the motor drifts 15%+ past a stripe.
        # Only applied when _move_start_pos is None (motor idle or in coast settle).
        # Gate 2 (active move): removed entirely — _tracker_on_black already handles
        # the "motor starts on a stripe" case (no rising edge fires if already black),
        # and the 35-50% thresholds we tried were the direct cause of pocket skips.
        min_ticks_idle = max(1, self._ticks_per_pocket * 15 // 100)
        # ── diagnostic state ──────────────────────────────────────
        _sample_count: int = 0
        _black_entry_pos: int | None = None   # encoder pos when stripe started
        _black_entry_time: float | None = None
        _last_raw_log_time: float = time.monotonic()
        RAW_LOG_INTERVAL = 0.25  # log raw IR reading every 250ms while moving
        try:
            while True:
                await asyncio.sleep(SAMPLE_INTERVAL)
                _sample_count += 1
                try:
                    raw = float(self.light_sensor.read())
                    reading = self._is_black_from_raw(raw)
                except Exception as e:
                    self.warn(f"IR tracker sensor read failed: {e}")
                    continue

                pos = self.motor.get_position()
                now = time.monotonic()

                # ── periodic raw signal heartbeat ─────────────────
                if now - _last_raw_log_time >= RAW_LOG_INTERVAL:
                    low, high = self.hysteresis_thresholds
                    self.trace(
                        f"[IR-RAW] raw={raw:.0f} pocket={self._current_pocket} "
                        f"pos={pos} on_black={self._tracker_on_black} "
                        f"thresholds=[{low:.0f},{high:.0f}] "
                        f"move_start={self._move_start_pos} "
                        f"last_edge_pos={self._tracker_last_edge_pos}"
                    )
                    _last_raw_log_time = now

                # ── rising edge: white → black ─────────────────────
                if reading and not self._tracker_on_black:
                    delta = pos - self._tracker_last_edge_pos
                    move_start_delta = (pos - self._move_start_pos) if self._move_start_pos is not None else None
                    in_active_move = self._move_start_pos is not None

                    _black_entry_pos = pos
                    _black_entry_time = now

                    # During an active move we trust every rising edge EXCEPT a
                    # spurious one fired within the first min_ticks_idle ticks of the
                    # move: if the sensor was parked right at a stripe boundary,
                    # starting the motor jiggles it across the edge and it gets
                    # miscounted as a whole pocket (observed: delta_move_start=-3 →
                    # revolver under-rotated by one pocket, which corrupted the eject
                    # sweep and dropped only half the drums). A genuinely-adjacent
                    # stripe at rest already reads black, so no rising edge fires and
                    # this gate cannot swallow a real first stripe. The gate is keyed
                    # off the distance from the move start, NOT the last edge, so it
                    # never re-introduces the mid-move pocket skips that killed the
                    # old 35-50% active-move thresholds.
                    #
                    # While idle (coast settle or parked): Gate 1 blocks tiny drift
                    # back into a stripe the motor just coasted past (observed: ~227
                    # ticks = 0.17% of pocket). Threshold = 15% of pocket.
                    if in_active_move:
                        gate_ok = move_start_delta is None or abs(move_start_delta) >= min_ticks_idle
                        gate_name = "move_start"
                        gate_delta = move_start_delta if move_start_delta is not None else delta
                    else:
                        gate_ok = abs(delta) >= min_ticks_idle
                        gate_name = "idle"
                        gate_delta = delta

                    if gate_ok:
                        direction = 1 if delta > 0 else -1
                        old = self._current_pocket
                        self._current_pocket = (old + direction) % NUM_POCKETS
                        self._last_entry_pos = pos
                        self._tracker_last_edge_pos = pos
                        self._at_midpoint = False
                        self.debug(
                            f"[IR-EDGE] COUNTED pocket {old} → {self._current_pocket} "
                            f"pos={pos} delta_last_edge={delta:+d} "
                            f"delta_move_start={move_start_delta} "
                            f"min_idle={min_ticks_idle} raw={raw:.0f} "
                            f"gate={'none(active)' if in_active_move else 'idle'}"
                        )
                    else:
                        self.warn(
                            f"[IR-EDGE] REJECTED edge at pos={pos} "
                            f"pocket={self._current_pocket} raw={raw:.0f} "
                            f"delta_last_edge={delta:+d} "
                            f"delta_move_start={move_start_delta} "
                            f"move_start_pos={self._move_start_pos} "
                            f"reason=[gate_{gate_name} FAILED (|delta|={abs(gate_delta)} < min_idle={min_ticks_idle})]"
                        )

                # ── falling edge: black → white ────────────────────
                elif not reading and self._tracker_on_black:
                    if _black_entry_pos is not None and _black_entry_time is not None:
                        stripe_ticks = abs(pos - _black_entry_pos)
                        stripe_ms = (now - _black_entry_time) * 1000
                        self.debug(
                            f"[IR-FALL] stripe exit pos={pos} "
                            f"stripe_width={stripe_ticks} ticks "
                            f"stripe_duration={stripe_ms:.1f}ms "
                            f"pocket={self._current_pocket} raw={raw:.0f}"
                        )
                    _black_entry_pos = None
                    _black_entry_time = None

                self._tracker_on_black = reading
        except asyncio.CancelledError:
            raise

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
        """Run coro_fn() with stall-retry: backs up and retries up to self.stall_retries times."""
        retries = self.stall_retries
        for attempt in range(1, retries + 1):
            try:
                await coro_fn()
                return
            except MotorStalledError:
                self.motor.set_speed(0)  # passive brake
                if attempt >= retries:
                    self.warn(f"Motor stalled after {retries} attempts — giving up")
                    raise
                self.warn(f"Motor stalled (attempt {attempt}/{retries}) — backing up to retry")
                self.motor.set_velocity(int(FULL_VELOCITY * 0.7) * backup_sign)
                await asyncio.sleep(0.7)
                self.motor.set_speed(0)  # stop before retry so stall checker starts clean
                await asyncio.sleep(0.05)

    # ── navigation ───────────────────────────────────────────────

    async def advance(self, pockets: int = 1, *, precise: bool = False, velocity_factor: float = 1.0) -> None:
        """Move forward N pockets (black stripes)."""
        if self.motor_locked:
            self.warn(f"advance({pockets}) ignored — drum motor locked (emergency)")
            return
        self.debug(f"advance({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=True, precise=precise, velocity=int(FULL_VELOCITY * velocity_factor))

    async def retreat(self, pockets: int = 1, *, precise: bool = False, velocity_factor: float = 1.0) -> None:
        """Move backward N pockets."""
        if self.motor_locked:
            self.warn(f"retreat({pockets}) ignored — drum motor locked (emergency)")
            return
        self.debug(f"retreat({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=False, precise=precise, velocity=int(FULL_VELOCITY * velocity_factor))

    async def eject(self, pockets: int = 1) -> None:
        if self.motor_locked:
            self.warn(f"eject({pockets}) ignored — drum motor locked (emergency)")
            return
        self.debug(f"eject({pockets}) from pocket {self._current_pocket}")
        assert self.is_calibrated
        await self._move(pockets, forward=False, velocity=int(FULL_VELOCITY * 0.8))


    async def go_to_pocket(
        self,
        pocket: int,
        *,
        precise: bool = False,
        occupied: "set[int] | frozenset[int] | None" = None,
    ) -> str:
        if self.motor_locked:
            self.warn(f"go_to_pocket({pocket}) ignored — drum motor locked (emergency)")
            return "none"
        delta = (pocket - self._current_pocket) % NUM_POCKETS
        if delta == 0:
            self.debug(f"Already at pocket {pocket}")
            return "none"

        forward_steps = delta
        backward_steps = NUM_POCKETS - delta

        if occupied:
            cur = self._current_pocket
            fwd_path = {(cur + i) % NUM_POCKETS for i in range(1, forward_steps)}
            bwd_path = {(cur - i) % NUM_POCKETS for i in range(1, backward_steps)}
            fwd_cross = len(fwd_path & occupied)
            bwd_cross = len(bwd_path & occupied)

            if fwd_cross != bwd_cross:
                choose_forward = fwd_cross < bwd_cross
            else:
                choose_forward = forward_steps <= backward_steps

            if fwd_cross > 0 and bwd_cross > 0:
                self.warn(
                    f"go_to_pocket({pocket}) from {cur}: both directions cross "
                    f"occupied pockets (fwd={fwd_cross} via {sorted(fwd_path & occupied)}, "
                    f"bwd={bwd_cross} via {sorted(bwd_path & occupied)}) — "
                    f"picking {'forward' if choose_forward else 'backward'} (fewer crossings)"
                )
            else:
                self.debug(
                    f"go_to_pocket({pocket}) from {cur}: fwd_cross={fwd_cross} "
                    f"bwd_cross={bwd_cross} → {'forward' if choose_forward else 'backward'}"
                )
        else:
            choose_forward = forward_steps <= NUM_POCKETS // 2

        if choose_forward:
            await self.advance(forward_steps, precise=precise)
            return "forward"
        else:
            await self.retreat(backward_steps, precise=precise)
            return "backward"

    async def go_to_edge(self, target_edge: int) -> str:
        """Compat: convert edge to pocket and go there."""
        return await self.go_to_pocket(target_edge // 2)

    async def _move(self, pockets: int, *, forward: bool, precise: bool = True, velocity: int = FULL_VELOCITY) -> None:
        """Move N pockets with stall detection and automatic retry.

        The target pocket is anchored ONCE, up front, from the pocket we're
        currently at. ``_do_move`` then re-derives the *remaining* distance to
        that fixed target from the (tracker-updated) current pocket on every
        retry attempt, so pockets already crossed before a stall are not
        re-walked — and the retry never over-rotates past the intended slot.
        """
        assert 0 < pockets < NUM_POCKETS, f"pockets must be 1..{NUM_POCKETS - 1}"
        sign = 1 if forward else -1
        backup_sign = -sign
        target_pocket = (self._current_pocket + pockets * sign) % NUM_POCKETS
        await self._retry_on_stall(
            lambda: self._do_move(target_pocket, forward=forward, precise=precise, velocity=velocity),
            backup_sign=backup_sign,
        )

    async def _do_move(self, target_pocket: int, *, forward: bool, precise: bool = True, velocity: int = FULL_VELOCITY) -> None:
        """Move to target_pocket, trusting the continuous IR tracker for position.

        The background tracker owns _current_pocket. This method commands
        the motor and waits for the index to reach target, so coast-through
        after stop is handled for free — it simply updates the index while
        we're in the settling pause.

        Called fresh on every stall-retry attempt with the same fixed
        target_pocket; the remaining distance is recomputed from whatever
        _current_pocket the tracker landed on, so only the pockets not yet
        covered are retried.
        """
        assert self._ticks_per_pocket is not None, "Calibrate first (need ticks_per_pocket)"
        sign = 1 if forward else -1
        stall_check = self._make_stall_checker(direction=sign)

        if self._tracker_task is None or self._tracker_task.done():
            self.start_position_tracking()

        start_pocket = self._current_pocket
        if start_pocket == target_pocket:
            self.debug(f"_do_move: already at target pocket {target_pocket}, nothing to retry")
            return
        pockets = (target_pocket - start_pocket) % NUM_POCKETS if forward else (start_pocket - target_pocket) % NUM_POCKETS
        self.debug(
            f"{'fwd' if forward else 'bwd'} {pockets} pockets remaining "
            f"{'precise' if precise else 'fast'} "
            f"(from {start_pocket} → {target_pocket}, midpoint={self._at_midpoint})"
        )

        self._move_start_pos = self.motor.get_position()
        expected_ticks = pockets * self._ticks_per_pocket
        low, high = self.hysteresis_thresholds
        raw_at_start = float(self.light_sensor.read())
        self.debug(
            f"[MOVE-START] pos={self._move_start_pos} pocket={start_pocket} "
            f"target={target_pocket} expected_ticks={expected_ticks} "
            f"IR_raw={raw_at_start:.0f} thresholds=[{low:.0f},{high:.0f}] "
            f"velocity={velocity * sign}"
        )
        self.motor.set_velocity(velocity * sign)

        try:
            while self._current_pocket != target_pocket:
                stall_check()
                await asyncio.sleep(SAMPLE_INTERVAL)
        except MotorStalledError:
            # Lift the move-start gate BEFORE the stall propagates. Otherwise the
            # back-up in _retry_on_stall runs with a stale _move_start_pos still
            # set, so the tracker stays in its active-move gate and mis-counts the
            # back-up crossings — which corrupts the remaining distance the next
            # retry attempt recomputes from _current_pocket.
            self._move_start_pos = None
            raise

        pos_at_stop = self.motor.get_position()
        actual_ticks = abs(pos_at_stop - self._move_start_pos)
        raw_at_stop = float(self.light_sensor.read())
        self.motor.set_velocity(0)
        self.debug(
            f"[MOVE-STOP] pos={pos_at_stop} pocket={self._current_pocket} "
            f"actual_ticks={actual_ticks} expected_ticks={expected_ticks} "
            f"tick_error={actual_ticks - expected_ticks:+d} "
            f"IR_raw={raw_at_stop:.0f}"
        )
        self._move_start_pos = None  # lift the move-start gate

        # Let the tracker absorb any coast through the next stripe.
        pocket_before_coast = self._current_pocket
        settle_deadline = time.monotonic() + COAST_SETTLE_SECONDS
        while time.monotonic() < settle_deadline:
            await asyncio.sleep(SAMPLE_INTERVAL)

        pos_after_coast = self.motor.get_position()
        coast_ticks = abs(pos_after_coast - pos_at_stop)
        raw_after_coast = float(self.light_sensor.read())
        self.debug(
            f"[COAST] coast_ticks={coast_ticks} "
            f"pocket_before={pocket_before_coast} pocket_after={self._current_pocket} "
            f"IR_raw={raw_after_coast:.0f} pos={pos_after_coast}"
        )

        if self._current_pocket != target_pocket:
            await self._reconcile_drift(target_pocket)

        if precise:
            await self._center_on_stripe(self._last_entry_pos)

        self._at_midpoint = False
        self.debug(f"[MOVE-DONE] pocket={self._current_pocket} target={target_pocket}")

    async def _reconcile_drift(self, target_pocket: int) -> None:
        """Drive the revolver physically back onto ``target_pocket`` after a coast-through.

        The open-loop move in ``_do_move`` stops the motor the instant the
        tracker reaches target, so the revolver can coast through the next
        stripe during the settle pause and land one pocket past target.
        Accepting that drifted index (the old behaviour) silently desynced the
        physical pocket from the slot bookkeeping: the drum was then loaded one
        pocket off, and a later drum got routed into the already-occupied
        pocket. Instead, drive a closed-loop ``move_to_position`` back to the
        target stripe — it decelerates and holds, so it does not coast — then
        resync the tracker index. After this the drum lands in exactly the
        assigned slot, physically and logically.
        """
        drift = (self._current_pocket - target_pocket) % NUM_POCKETS
        if drift > NUM_POCKETS // 2:
            drift -= NUM_POCKETS
        self.warn(
            f"[COAST-DRIFT] target={target_pocket}, actual={self._current_pocket} "
            f"({drift:+d} pockets) — correcting to land physically on target"
        )
        if self.motor_locked or self._ticks_per_pocket is None:
            self.warn("[COAST-DRIFT] cannot correct (locked/uncalibrated) — tracker authoritative")
            return

        # Pocket index increases with encoder position (forward = +ticks). The
        # last counted stripe is the drifted pocket; the target stripe sits
        # ``signed`` pockets away in encoder space.
        signed = -drift  # signed pocket delta from current → target
        target_pos = self._tracker_last_edge_pos + signed * self._ticks_per_pocket

        self.motor.move_to_position(FULL_VELOCITY, target_pos)
        deadline = time.monotonic() + DRIFT_CORRECTION_TIMEOUT
        while not self.motor.is_done():
            if time.monotonic() > deadline:
                self.warn("[COAST-DRIFT] correction move timed out — braking")
                break
            await asyncio.sleep(SAMPLE_INTERVAL)
        self.motor.set_velocity(0)

        # Brief settle, then resync: we drove a closed-loop move to the target
        # stripe, so both the physical revolver and the tracker index are now
        # on target. Force the index (belt-and-suspenders if the tracker missed
        # the crossing) and reset the edge reference to here.
        settle_deadline = time.monotonic() + COAST_SETTLE_SECONDS
        while time.monotonic() < settle_deadline:
            await asyncio.sleep(SAMPLE_INTERVAL)
        pos = self.motor.get_position()
        self._current_pocket = target_pocket
        self._tracker_last_edge_pos = pos
        self._last_entry_pos = pos
        self.info(f"[COAST-DRIFT] corrected → pocket {target_pocket} (pos={pos})")

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
        if self.motor_locked:
            self.warn("move_to_midpoint ignored — drum motor locked (emergency)")
            return
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
        if self.motor_locked:
            self.warn("move_from_midpoint ignored — drum motor locked (emergency)")
            return
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

    async def turn_relative(
        self, slots: float, *, forward: bool, speed: float = 1.0
    ) -> None:
        """Turn the drum by a relative number of slots, not snapping to pockets.

        Unlike advance()/retreat() (which target whole stripe positions), this
        rotates the drum a free relative amount. One slot equals one pocket
        (_ticks_per_pocket ticks); fractional slots are allowed.

        The background IR tracker stays authoritative for _current_pocket and
        counts any stripes crossed during the turn, so the pocket index remains
        correct afterwards.
        """
        if self.motor_locked:
            self.warn(
                f"turn_relative({slots}) ignored — drum motor locked (emergency)"
            )
            return
        assert self._ticks_per_pocket is not None, "Calibrate first (need ticks_per_pocket)"
        sign = 1 if forward else -1
        ticks = round(abs(slots) * self._ticks_per_pocket)
        velocity = max(1, int(FULL_VELOCITY * speed))
        self.debug(
            f"turn_relative({slots:+.2f} slots, {'fwd' if forward else 'bwd'}) "
            f"= {ticks} ticks @ velocity {velocity * sign}"
        )
        if ticks == 0:
            return

        async def _do():
            stall_check = self._make_stall_checker(direction=sign)
            start = self.motor.get_position()
            self.motor.set_velocity(velocity * sign)
            while abs(self.motor.get_position() - start) < ticks:
                stall_check()
                await asyncio.sleep(SAMPLE_INTERVAL)
            self.motor.set_velocity(0)

        await self._retry_on_stall(_do, backup_sign=-sign)
        self._at_midpoint = False
