from raccoon import GenericRobot, RobotService

NUM_SLOTS = 9
# Game layout: 9 slots, 4 blue + 4 pink drums, slot 4 stays empty.
TOTAL_BLUE = 4
TOTAL_PINK = 4
TOTAL_DRUMS = TOTAL_BLUE + TOTAL_PINK

# First drum uses the empirically known timeout; learning refines from there.
DEFAULT_DETECTION_TIMEOUT = 0.8
# Safety margin added on top of the learned average.
TIMING_MARGIN = 1.05  # +5 %


class SortingService(RobotService):
    """Bidirectional revolver sorting: blue grows CW (0→1→2→...),
    pink grows CCW (8→7→6→...). Empty slot ends up in the middle."""

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self.blue_next: int = 0
        self.pink_next: int = 8
        self.slots: list[str | None] = [None] * NUM_SLOTS
        self._blue_detected: int = 0
        self._pink_detected: int = 0
        self._detection_deltas: list[float] = []

    def assign_slot(self, color: str) -> int:
        """Return the target slot for *color* and advance the pointer."""
        if self.blue_next > self.pink_next:
            raise RuntimeError(
                f"Revolver full: blue_next={self.blue_next}, pink_next={self.pink_next}",
            )

        if color == "blue" and self._blue_detected >= TOTAL_BLUE:
            self.warn(f"Max blue ({TOTAL_BLUE}) already collected — reassigning to pink")
            color = "pink"
        elif color == "pink" and self._pink_detected >= TOTAL_PINK:
            self.warn(f"Max pink ({TOTAL_PINK}) already collected — reassigning to blue")
            color = "blue"

        if color == "blue":
            target = self.blue_next
            self.blue_next += 1
            self._blue_detected += 1
        elif color == "pink":
            target = self.pink_next
            self.pink_next -= 1
            self._pink_detected += 1
        else:
            raise ValueError(f"Unknown color: {color!r}")

        self.slots[target] = color
        self.info(
            f"Assigned {color} → slot {target}  "
            f"(blue_next={self.blue_next}, pink_next={self.pink_next})",
        )
        return target

    def guess_color(self) -> str:
        """Guess the most likely remaining color. Deterministic argmax.

        Example: 3 blue already detected, 1 pink already detected, totals
        4/4 → remaining = 1 blue, 3 pink → pick pink (75 %).
        Ties go to whichever side still has a slot free; if both sides
        are tied and non-empty, prefer blue arbitrarily.
        """
        blue_remaining = max(0, TOTAL_BLUE - self._blue_detected)
        pink_remaining = max(0, TOTAL_PINK - self._pink_detected)
        total_remaining = blue_remaining + pink_remaining

        if total_remaining == 0:
            self.warn("All drums accounted for — defaulting to blue")
            return "blue"

        blue_probability = blue_remaining / total_remaining
        pink_probability = pink_remaining / total_remaining

        if pink_remaining > blue_remaining:
            guess = "pink"
        elif blue_remaining > pink_remaining:
            guess = "blue"
        else:
            guess = "blue"

        self.info(
            f"Color guess: {guess} "
            f"(blue remaining: {blue_remaining}/{TOTAL_BLUE}, "
            f"pink remaining: {pink_remaining}/{TOTAL_PINK}, "
            f"P(blue)={blue_probability:.0%}, P(pink)={pink_probability:.0%})"
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
        Falls back to a generous default if no data yet.
        """
        if not self._detection_deltas:
            return DEFAULT_DETECTION_TIMEOUT
        max_delta = max(self._detection_deltas)
        timeout = max(max_delta * TIMING_MARGIN, max_delta + 0.050)
        return max(timeout, 0.05)  # floor at 50 ms

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
