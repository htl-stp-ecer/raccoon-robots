from raccoon import GenericRobot, RobotService

NUM_SLOTS = 9
# Game layout: 9 slots, 4 blue + 4 pink drums, 1 empty.
#   Blue fills CCW from start pocket P: P → P-1 → P-2 → P-3
#   Pink fills CW  from P+1:            P+1 → P+2 → P+3 → P+4
# Both first targets are adjacent to the robot, and the gap between
# the two fronts always centres on (P+5) % 9.
# Seeds are set dynamically via set_start_pocket(); defaults to P=0.
TOTAL_BLUE = 4
TOTAL_PINK = 4
TOTAL_DRUMS = TOTAL_BLUE + TOTAL_PINK

# First drum uses the empirically known timeout; learning refines from there.
DEFAULT_DETECTION_TIMEOUT = 0.8
# Safety margin added on top of the learned average.
TIMING_MARGIN = 1.05  # +5 %
# Minimum absolute margin on top of max observed delta.
TIMING_ADDITIVE_MARGIN = 0.300  # 300 ms — prevents a single near-zero delta from collapsing the timeout
# Minimum number of successful detections before we trust the learned value.
MIN_SAMPLES_TO_LEARN = 3


class SortingService(RobotService):
    """Bidirectional revolver sorting with dynamic seed anchoring.

    Blue grows CCW from the start pocket, pink grows CW from start+1.
    Call ``set_start_pocket(pocket)`` before the first drum to anchor
    both groups adjacent to the robot's current position.
    """

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self.blue_next: int = 0   # decrements (mod 9): CCW
        self.pink_next: int = 1   # increments:          CW
        self.slots: list[str | None] = [None] * NUM_SLOTS
        self._blue_detected: int = 0
        self._pink_detected: int = 0
        self._detection_deltas: list[float] = []

    def set_start_pocket(self, pocket: int) -> None:
        """Anchor both colour groups to the robot's current pocket.

        Blue starts at *pocket* and grows CCW; pink starts at *pocket + 1*
        and grows CW.  Both first targets are adjacent to the robot, and
        the gap naturally centres on the diametrically opposite point
        ``(pocket + 5) % 9``.

        Must be called **before** the first ``assign_slot``.
        """
        if self._blue_detected + self._pink_detected > 0:
            self.warn("set_start_pocket called after drums already assigned — ignoring")
            return
        self.blue_next = pocket % NUM_SLOTS
        self.pink_next = (pocket + 1) % NUM_SLOTS
        self.info(
            f"Seeds anchored to pocket {pocket}: "
            f"blue_next={self.blue_next} (CCW), pink_next={self.pink_next} (CW)"
        )

    def assign_slot(self, color: str) -> int:
        """Return the target slot for *color* and advance the pointer.

        If the colour's next slot is already occupied (detection error
        causing a >4 split), the drum is silently redirected to the
        other colour's side so the revolver doesn't jam.
        """
        if color not in ("blue", "pink"):
            raise ValueError(f"Unknown color: {color!r}")

        # Determine primary target from the colour's pointer.
        if color == "blue":
            target = self.blue_next
        else:
            target = self.pink_next

        # If the primary target is already taken, redirect to the other side.
        if self.slots[target] is not None:
            other = "pink" if color == "blue" else "blue"
            other_target = self.pink_next if color == "blue" else self.blue_next
            if self.slots[other_target] is not None:
                raise RuntimeError(
                    f"Revolver full: blue_next={self.blue_next} "
                    f"({self.slots[self.blue_next]}), "
                    f"pink_next={self.pink_next} "
                    f"({self.slots[self.pink_next]})",
                )
            self.warn(
                f"{color} side full at slot {target}, "
                f"redirecting to {other} at slot {other_target}",
            )
            color = other
            target = other_target

        # Commit the assignment and advance the pointer.
        self.slots[target] = color
        if color == "blue":
            self.blue_next = (target - 1) % NUM_SLOTS  # CCW
            self._blue_detected += 1
        else:
            self.pink_next = (target + 1) % NUM_SLOTS  # CW
            self._pink_detected += 1

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
        """Indices of blue-occupied slots, in ring order (CCW from 0)."""
        return [i for i, s in enumerate(self.slots) if s == "blue"]

    @property
    def pink_slots(self) -> list[int]:
        """Indices of pink-occupied slots, in ring order (CW from 1)."""
        return [i for i, s in enumerate(self.slots) if s == "pink"]

    @staticmethod
    def ring_contiguous_endpoints(slots: list[int]) -> tuple[int, int]:
        """Return (start, end) of a ring-contiguous group of slot indices.

        Finds the largest gap between consecutive occupied slots on the
        ring.  The contiguous arc starts right after that gap and ends
        right before it.  For non-wrapping groups this is simply
        (min, max); for groups that wrap around 0 it correctly returns
        e.g. (6, 0) for the set {0, 6, 7, 8}.
        """
        if len(slots) <= 1:
            return (slots[0], slots[0])
        s = sorted(slots)
        max_gap = 0
        max_gap_after = 0  # index in `s` right after the biggest gap
        for i in range(len(s)):
            nxt = (i + 1) % len(s)
            gap = (s[nxt] - s[i]) % NUM_SLOTS
            if gap > max_gap:
                max_gap = gap
                max_gap_after = nxt
        start = s[max_gap_after]
        end = s[(max_gap_after - 1) % len(s)]
        return start, end

    @property
    def empty_slot(self) -> int | None:
        """The single empty slot (None if revolver isn't full yet or has >1 empty)."""
        empties = [i for i, s in enumerate(self.slots) if s is None]
        return empties[0] if len(empties) == 1 else None

    @staticmethod
    def _ring_distance(a: int, b: int) -> int:
        d = abs(a - b)
        return min(d, NUM_SLOTS - d)

    def nearest_empty_slot(self, current_index: int) -> int:
        """Return the empty slot nearest to current_index (shortest path on ring)."""
        empties = [i for i, s in enumerate(self.slots) if s is None]
        if not empties:
            raise RuntimeError("No empty slots available")

        best = min(empties, key=lambda e: self._ring_distance(current_index, e))
        self.info(f"Nearest empty slot to {current_index}: slot {best} (empties={empties})")
        return best

    def strategic_empty_slot(self, current_index: int) -> int:
        """Pick the staging slot that minimises worst-case travel to the next drum target.

        Core idea: stage in the **center of the gap** between the two colour
        fronts so that both ``blue_next`` and ``pink_next`` are reachable via
        short, clear paths through the unfilled zone.

        Special cases:
        * One colour fully placed → stage near the remaining colour's next target.
        * Both colours done → fall back to nearest empty.
        """
        empties = [i for i, s in enumerate(self.slots) if s is None]
        if not empties:
            raise RuntimeError("No empty slots available")

        blue_remaining = TOTAL_BLUE - self._blue_detected
        pink_remaining = TOTAL_PINK - self._pink_detected

        # ── all drums placed ──────────────────────────────────────
        if blue_remaining == 0 and pink_remaining == 0:
            best = min(empties, key=lambda e: self._ring_distance(current_index, e))
            self.info(f"Strategic empty (all done): slot {best}")
            return best

        # ── only one colour remaining ─────────────────────────────
        if blue_remaining == 0:
            best = min(empties, key=lambda e: (
                self._ring_distance(e, self.pink_next),
                self._ring_distance(current_index, e),
            ))
            self.info(
                f"Strategic empty (only pink left, next={self.pink_next}): slot {best}"
            )
            return best

        if pink_remaining == 0:
            best = min(empties, key=lambda e: (
                self._ring_distance(e, self.blue_next),
                self._ring_distance(current_index, e),
            ))
            self.info(
                f"Strategic empty (only blue left, next={self.blue_next}): slot {best}"
            )
            return best

        # ── both colours expected: centre of gap ──────────────────
        # The gap runs CW from pink_next to blue_next (the unfilled zone
        # between the two growing fronts).  Its centre is the point
        # that equalises the distance to both next targets.
        #
        # Because blue grows CCW and pink CW, the gap arc goes CW from
        # pink_next around to blue_next.  Midpoint on that arc:
        gap_cw = (self.blue_next - self.pink_next) % NUM_SLOTS
        ideal = (self.pink_next + (gap_cw + 1) // 2) % NUM_SLOTS

        # Pick the empty slot closest to the ideal, with a tie-break
        # on distance from our current position (less travel to stage).
        best = min(empties, key=lambda e: (
            self._ring_distance(e, ideal),
            self._ring_distance(current_index, e),
        ))

        self.info(
            f"Strategic empty (blue_next={self.blue_next}, pink_next={self.pink_next}, "
            f"ideal={ideal}): slot {best} (empties={empties})"
        )
        return best
