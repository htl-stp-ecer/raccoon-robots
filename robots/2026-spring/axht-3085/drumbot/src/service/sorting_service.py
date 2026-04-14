from raccoon import GenericRobot, RobotService

NUM_SLOTS = 9
# Game layout: 9 slots, 4 blue + 4 pink drums, slot 4 stays empty.
TOTAL_BLUE = 4
TOTAL_PINK = 4
TOTAL_DRUMS = TOTAL_BLUE + TOTAL_PINK

# First drum uses the empirically known timeout; learning refines from there.
DEFAULT_DETECTION_TIMEOUT = 1.2
# Safety margin added on top of the learned average.
TIMING_MARGIN = 1.15  # +15 %
# Minimum absolute margin on top of max observed delta.
TIMING_ADDITIVE_MARGIN = 0.500  # 500 ms — prevents a single near-zero delta from collapsing the timeout
# Minimum number of successful detections before we trust the learned value.
MIN_SAMPLES_TO_LEARN = 3


class SortingService(RobotService):
    """Proximity-aware bidirectional revolver sorting.

    Two color groups grow inward from opposite ends:
        lo_color:  0 → 1 → 2 → 3
        hi_color:  8 → 7 → 6 → 5
        (gap at slot 4)

    Which color gets which side is decided by the first drum: it goes to
    whichever end is nearest to the current pocket.  This ensures consecutive
    same-color drums are always 1 slot apart, and switching colors routes
    through the empty gap — never over filled slots.
    """

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self._lo_next: int = 0   # always increments
        self._hi_next: int = 8   # always decrements
        self._lo_color: str | None = None
        self._hi_color: str | None = None
        self.slots: list[str | None] = [None] * NUM_SLOTS
        self._blue_detected: int = 0
        self._pink_detected: int = 0
        self._detection_deltas: list[float] = []

    def _lock_sides(self, first_color: str, current_pocket: int) -> None:
        """Assign first color to whichever end is nearest to current pocket."""
        def ring_dist(a: int, b: int) -> int:
            d = abs(a - b)
            return min(d, NUM_SLOTS - d)

        dist_lo = ring_dist(current_pocket, 0)
        dist_hi = ring_dist(current_pocket, NUM_SLOTS - 1)

        if dist_lo <= dist_hi:
            self._lo_color = first_color
        else:
            self._lo_color = "pink" if first_color == "blue" else "blue"
        self._hi_color = "pink" if self._lo_color == "blue" else "blue"
        self.info(
            f"Sides locked (first={first_color}, pocket={current_pocket}, "
            f"dist_lo={dist_lo}, dist_hi={dist_hi}): "
            f"{self._lo_color} → 0→3, {self._hi_color} → 8→5"
        )

    @property
    def blue_next(self) -> int:
        if self._lo_color == "blue":
            return self._lo_next
        return self._hi_next

    @property
    def pink_next(self) -> int:
        if self._lo_color == "pink":
            return self._lo_next
        return self._hi_next

    def assign_slot(self, color: str, current_pocket: int = 0) -> int:
        """Return the target slot for *color* and advance the pointer.

        *current_pocket* is used to decide side assignment for the first drum.
        """
        if color not in ("blue", "pink"):
            raise ValueError(f"Unknown color: {color!r}")

        if self._lo_color is None:
            self._lock_sides(color, current_pocket)

        if self._lo_next > self._hi_next:
            raise RuntimeError(
                f"Revolver full: lo_next={self._lo_next}, hi_next={self._hi_next}",
            )

        if color == self._lo_color:
            target = self._lo_next
            self._lo_next += 1
        else:
            target = self._hi_next
            self._hi_next -= 1

        if color == "blue":
            self._blue_detected += 1
        else:
            self._pink_detected += 1

        self.slots[target] = color
        self.info(
            f"Assigned {color} → slot {target}  "
            f"(lo[{self._lo_color}]={self._lo_next}, "
            f"hi[{self._hi_color}]={self._hi_next})",
        )
        return target

    def guess_color(self, current_pocket: int = 0) -> str:
        """Guess the most likely remaining color.

        If one color has more drums remaining, pick that one.
        On a tie, pick whichever color's next slot is **nearest** to the
        current pocket — this prevents ping-ponging across the revolver
        when the camera fails repeatedly.
        """
        blue_remaining = max(0, TOTAL_BLUE - self._blue_detected)
        pink_remaining = max(0, TOTAL_PINK - self._pink_detected)
        total_remaining = blue_remaining + pink_remaining

        if total_remaining == 0:
            self.warn("All drums accounted for — defaulting to blue")
            return "blue"

        if pink_remaining > blue_remaining:
            guess = "pink"
        elif blue_remaining > pink_remaining:
            guess = "blue"
        elif self._lo_color is not None:
            # Tie — pick whichever color's next slot is closer.
            def ring_dist(a: int, b: int) -> int:
                d = abs(a - b)
                return min(d, NUM_SLOTS - d)

            lo_dist = ring_dist(current_pocket, self._lo_next)
            hi_dist = ring_dist(current_pocket, self._hi_next)
            guess = self._lo_color if lo_dist <= hi_dist else self._hi_color
        else:
            guess = "blue"

        self.info(
            f"Color guess: {guess} "
            f"(blue remaining: {blue_remaining}/{TOTAL_BLUE}, "
            f"pink remaining: {pink_remaining}/{TOTAL_PINK}, "
            f"pocket={current_pocket})"
        )
        return guess

    # ── Adaptive timeout learning ──────────────────────────────────

    def record_detection_delta(self, delta: float) -> None:
        """Record how long after polling start the camera detected a drum."""
        self._detection_deltas.append(delta)
        self.info(
            f"Detection delta: {delta:.3f}s "
            f"(history: {[f'{d:.3f}' for d in self._detection_deltas]})"
        )

    @property
    def learned_timeout(self) -> float:
        """Return adaptive timeout based on past detections + safety margin.

        Uses the *maximum* observed delta (not average) plus margin,
        so we don't close too early on a slightly slower drum.
        Falls back to a generous default if no data yet or too few samples.

        Requires MIN_SAMPLES_TO_LEARN successful detections before trusting
        the learned value — a single early detection (e.g. drum already
        present when the step starts) would otherwise collapse the timeout
        to near-zero and cause all subsequent drums to be missed.
        """
        if len(self._detection_deltas) < MIN_SAMPLES_TO_LEARN:
            return DEFAULT_DETECTION_TIMEOUT
        max_delta = max(self._detection_deltas)
        timeout = max(max_delta * TIMING_MARGIN, max_delta + TIMING_ADDITIVE_MARGIN)
        return max(timeout, DEFAULT_DETECTION_TIMEOUT)  # never go below the default

    @property
    def blue_slots(self) -> list[int]:
        """Indices of blue-occupied slots, in filling order (ascending)."""
        return [i for i, s in enumerate(self.slots) if s == "blue"]

    @property
    def pink_slots(self) -> list[int]:
        """Indices of pink-occupied slots, in filling order (descending)."""
        return [i for i in range(NUM_SLOTS - 1, -1, -1) if self.slots[i] == "pink"]

    @property
    def empty_slot(self) -> int | None:
        """The single empty slot (None if revolver isn't full yet or has >1 empty)."""
        empties = [i for i, s in enumerate(self.slots) if s is None]
        return empties[0] if len(empties) == 1 else None

    def nearest_empty_slot(self, current_index: int) -> int:
        """Return the empty slot nearest to current_index (shortest path on ring)."""
        empties = [i for i, s in enumerate(self.slots) if s is None]
        if not empties:
            raise RuntimeError("No empty slots available")

        def ring_distance(a: int, b: int) -> int:
            d = abs(a - b)
            return min(d, NUM_SLOTS - d)

        best = min(empties, key=lambda e: ring_distance(current_index, e))
        self.info(f"Nearest empty slot to {current_index}: slot {best} (empties={empties})")
        return best

    @property
    def optimal_wait_slot(self) -> int:
        """Slot between the two fill fronts — minimises worst-case travel.

        Both groups grow in the same direction with the gap at slot 4.
        The optimal wait position is always the gap (slot 4) or whichever
        front is about to be filled next, since both are reachable through
        empty space.
        """
        if self._lo_color is None:
            return (NUM_SLOTS - 1) // 2  # sides not locked yet; centre is safe
        return (self._lo_next + self._hi_next) // 2
