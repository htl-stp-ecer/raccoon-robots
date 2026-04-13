"""Hard edge-case tests for the drum sorting / ejection pipeline.

These tests guard against the "only 3 drums ejected instead of 4" class of
bugs and the subtler failures around imperfect sorting state, non-standard
starting positions, and partial intake (missed drums). They simulate the
revolver mechanically with a FakeDrumMotor so the tests are deterministic
and do not require any hardware.

MECHANICAL MODEL
----------------
The revolver has NUM_POCKETS = 9 pockets. `current_pocket` is the pocket
index currently aligned with the physical ejection hole. A drum in pocket
X is ejected at the moment `current_pocket` transitions to X. Each call
to advance(1)/retreat(1) or a step of go_to_pocket() corresponds to one
such transition.

The fundamental invariant under test:

    After running EjectNearestColorStep on a sort state, every slot index
    that held a drum of the chosen color MUST have been under the ejection
    hole at some point during the sweep phase.

If even one slot is missed we count that as a drum stranded on the field —
the mission would lose points and the user's complaint is reproduced.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from src.service.drum_motor_service import NUM_POCKETS
from src.service.sorting_service import SortingService
from src.steps.drum_collector.sort_into_slot_step import (
    EJECT_HOLE_SLOT,
    EjectNearestColorStep,
    GoToEmptySlotStep,
    SortIntoSlotStep,
)


# ── Fake hardware ────────────────────────────────────────────────


@dataclass
class FakeDrumMotor:
    """Deterministic drum-motor stand-in that tracks every pocket transition.

    The key observable is `visited`: the ordered list of pockets that
    arrived at the ejection hole while the step was doing work. Tests
    assert against this list to verify that every target slot is swept
    across the hole.
    """

    current_pocket: int = 0
    at_midpoint: bool = False
    # Every time `current_pocket` changes to a new value, the new value
    # is appended here. This includes both the setup `go_to_pocket` and
    # the per-pocket advance/retreat steps.
    visited: list[int] = field(default_factory=list)
    calls: list[tuple] = field(default_factory=list)

    # ── helpers ──────────────────────────────────────────────────

    def _step(self, delta: int) -> None:
        self.current_pocket = (self.current_pocket + delta) % NUM_POCKETS
        self.visited.append(self.current_pocket)

    # ── DrumMotorService-compatible API ──────────────────────────

    async def go_to_pocket(self, pocket: int, *, precise: bool = False) -> str:
        pocket = pocket % NUM_POCKETS
        delta = (pocket - self.current_pocket) % NUM_POCKETS
        self.calls.append(("go_to_pocket", pocket))
        if delta == 0:
            return "none"
        if delta <= NUM_POCKETS // 2:
            for _ in range(delta):
                self._step(+1)
            self.at_midpoint = False
            return "forward"
        for _ in range(NUM_POCKETS - delta):
            self._step(-1)
        self.at_midpoint = False
        return "backward"

    async def go_to_pocket_via_gap(
        self, pocket: int, filled_slots: set[int], *, precise: bool = False
    ) -> str:
        """Simplified gap-aware navigation for tests — just delegates to go_to_pocket."""
        return await self.go_to_pocket(pocket, precise=precise)

    async def advance(self, pockets: int = 1, *, precise: bool = False) -> None:
        self.calls.append(("advance", pockets))
        for _ in range(pockets):
            self._step(+1)
        self.at_midpoint = False

    async def retreat(self, pockets: int = 1, *, precise: bool = False) -> None:
        self.calls.append(("retreat", pockets))
        for _ in range(pockets):
            self._step(-1)
        self.at_midpoint = False

    async def move_from_midpoint(self) -> None:
        self.calls.append(("move_from_midpoint",))
        self.at_midpoint = False

    async def move_to_midpoint(self) -> None:
        self.calls.append(("move_to_midpoint",))
        self.at_midpoint = True

    def info(self, msg: str) -> None:  # pragma: no cover - silenced
        pass

    def warn(self, msg: str) -> None:  # pragma: no cover - silenced
        pass


def make_robot(sorting: SortingService, motor: FakeDrumMotor) -> MagicMock:
    """Build a mock robot whose get_service routes to our fakes."""
    robot = MagicMock()

    from src.service.drum_motor_service import DrumMotorService

    def get_service(kind):
        if kind is SortingService:
            return sorting
        if kind is DrumMotorService:
            return motor
        raise KeyError(kind)

    robot.get_service.side_effect = get_service
    return robot


def run(coro):
    """Tiny event-loop helper so tests don't need pytest-asyncio."""
    return asyncio.new_event_loop().run_until_complete(coro)


def run_eject(
    sorting: SortingService, motor: FakeDrumMotor
) -> tuple[set[int], str | None, int]:
    """Run one EjectNearestColorStep call.

    Returns `(claimed_ejected, color, sweep_start_idx)` where:
      - claimed_ejected is the set of slot indices the step marked as
        emptied in `sorting.slots` (i.e., what the code believes it
        ejected — this is what we have to physically verify).
      - color is 'blue' or 'pink' (or None if there was nothing to do).
      - sweep_start_idx is the length of motor.visited *before* the
        step ran, so callers can slice to see only the new motion.
    """
    before = [c for c in sorting.slots]
    sweep_start_idx = len(motor.visited)

    step = EjectNearestColorStep()
    step.info = lambda msg: None
    step.warn = lambda msg: None
    run(step._execute_step(make_robot(sorting, motor)))

    after = [c for c in sorting.slots]
    claimed = {i for i in range(NUM_POCKETS)
               if before[i] is not None and after[i] is None}
    colors = {before[i] for i in claimed}
    color = next(iter(colors), None) if len(colors) <= 1 else None
    return claimed, color, sweep_start_idx


# ── Sort-state factories ─────────────────────────────────────────


def fill(*colors: str) -> SortingService:
    """Assign a sequence of colors to a fresh SortingService."""
    s = SortingService(MagicMock())
    s.info = lambda msg: None
    s.warn = lambda msg: None
    for c in colors:
        s.assign_slot(c)
    return s


def perfect() -> SortingService:
    """The expected end-of-intake state: 4 blue (0-3), 4 pink (5-8), empty 4."""
    return fill("blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink")


# ── The core invariant ──────────────────────────────────────────


def assert_all_ejected(
    motor: FakeDrumMotor, target_slots, *, since: int = 0
) -> None:
    """Every target slot must appear in motor.visited at or after `since`.

    `since` is the index into motor.visited where the step started. Using
    a slice lets us verify both (a) the step actually rotated every slot
    it claimed to eject, and (b) the setup motion didn't sweep drums of
    another color across the ejection hole.
    """
    target_set = set(target_slots)
    visited_during_sweep = motor.visited[since:]
    missing = sorted(target_set - set(visited_during_sweep))
    assert not missing, (
        f"Drums left in the revolver! slots {missing} were never rotated to "
        f"the ejection hole.\n"
        f"  target_slots = {sorted(target_set)}\n"
        f"  visited      = {motor.visited}\n"
        f"  sweep slice  = {visited_during_sweep}\n"
        f"  calls        = {motor.calls}"
    )


# ── The bug: off-by-one in pockets_to_eject ─────────────────────


class TestEjectAllFourDrums:
    """Regression tests for 'only 3 of 4 drums are ejected' bug.

    The step computes `pockets_to_eject = len(slots) - 1` and starts at
    `lo - 1` (or `hi + 1`). That is exactly one pocket short: the drum at
    the far end of the color group is never brought under the ejection
    hole. These tests reproduce that and also protect against any future
    regression that leaves even one drum behind.
    """

    def test_perfect_sort_first_eject_covers_every_claimed_slot(self):
        """Whichever color the step picks first, every slot it marks as
        ejected must have rotated through the ejection hole."""
        sorting = perfect()
        motor = FakeDrumMotor(current_pocket=4)
        claimed, color, since = run_eject(sorting, motor)
        assert len(claimed) == 4, (
            f"Step must claim to eject all 4 of {color}, got {claimed}"
        )
        assert_all_ejected(motor, claimed, since=since)

    def test_perfect_sort_second_eject_covers_every_claimed_slot(self):
        """After the first eject, the second call must fully clear the
        remaining color — this is the 'second sweep' the user reported
        losing drums on."""
        sorting = perfect()
        motor = FakeDrumMotor(current_pocket=4)
        run_eject(sorting, motor)  # whichever color was closer

        claimed2, color2, since2 = run_eject(sorting, motor)
        assert len(claimed2) == 4, (
            f"Second eject must clear 4 drums of the remaining color, "
            f"got {claimed2} ({color2})"
        )
        assert_all_ejected(motor, claimed2, since=since2)
        assert sorting.slots == [None] * NUM_POCKETS

    @pytest.mark.parametrize("start_pocket", list(range(NUM_POCKETS)))
    def test_eject_covers_all_claimed_from_any_starting_position(
        self, start_pocket
    ):
        """Regardless of where the revolver parked, every slot the step
        claims to eject must have been rotated under the ejection hole.
        This is the main regression test for the off-by-one in the
        sweep loop."""
        sorting = perfect()
        motor = FakeDrumMotor(current_pocket=start_pocket)

        claimed1, _, since1 = run_eject(sorting, motor)
        assert len(claimed1) == 4
        assert_all_ejected(motor, claimed1, since=since1)

        claimed2, _, since2 = run_eject(sorting, motor)
        assert len(claimed2) == 4
        assert_all_ejected(motor, claimed2, since=since2)

        assert sorting.slots == [None] * NUM_POCKETS, (
            f"Revolver not fully empty from start={start_pocket}: "
            f"{sorting.slots}"
        )

    @pytest.mark.parametrize("start_pocket", list(range(NUM_POCKETS)))
    def test_pink_only_from_any_starting_position(self, start_pocket):
        """Only pink drums loaded. Eject must clear all four from any
        starting position, forward or backward sweep alike."""
        sorting = fill("pink", "pink", "pink", "pink")
        motor = FakeDrumMotor(current_pocket=start_pocket)
        claimed, _, since = run_eject(sorting, motor)
        assert claimed == {0, 1, 2, 3}  # pink first → near side
        assert_all_ejected(motor, claimed, since=since)

    @pytest.mark.parametrize("start_pocket", list(range(NUM_POCKETS)))
    def test_blue_only_from_any_starting_position(self, start_pocket):
        """Only blue drums loaded. Must clear all four."""
        sorting = fill("blue", "blue", "blue", "blue")
        motor = FakeDrumMotor(current_pocket=start_pocket)
        claimed, _, since = run_eject(sorting, motor)
        assert claimed == {0, 1, 2, 3}
        assert_all_ejected(motor, claimed, since=since)

    def test_revolver_full_blue_then_pink(self):
        """9-drum full load: must cleanly eject every drum."""
        sorting = fill(*(["blue", "pink"] * 4), "blue")  # 5 blue, 4 pink
        assert sorting.slots.count(None) == 0
        motor = FakeDrumMotor(current_pocket=0)

        claimed1, _, since1 = run_eject(sorting, motor)
        assert_all_ejected(motor, claimed1, since=since1)
        claimed2, _, since2 = run_eject(sorting, motor)
        assert_all_ejected(motor, claimed2, since=since2)

        assert sorting.slots == [None] * NUM_POCKETS, (
            f"Revolver should be fully empty after two ejects, got "
            f"{sorting.slots}"
        )


# ── Imperfect sort: missed drum / wrong guess scenarios ─────────


class TestImperfectSortingState:
    """Simulate realistic failure modes from intake and assert we still
    eject every logged drum."""

    def _drain_and_verify(
        self, sorting: SortingService, motor: FakeDrumMotor
    ) -> None:
        """Repeatedly eject until empty, verifying every call's claim."""
        guard = 0
        while any(c is not None for c in sorting.slots):
            claimed, _, since = run_eject(sorting, motor)
            assert claimed, "Eject step returned without ejecting anything"
            assert_all_ejected(motor, claimed, since=since)
            guard += 1
            assert guard < 10, "Eject loop did not converge"

    def test_uneven_3_blue_5_pink(self):
        """Color detection skewed: 3 blues recognised, 5 pinks. With 8
        drums total the 'empty slot' is not where it normally is, which
        shifts every distance calculation."""
        sorting = fill("blue", "blue", "blue",
                       "pink", "pink", "pink", "pink", "pink")
        assert sorting.blue_slots == [0, 1, 2]
        assert sorted(sorting.pink_slots) == [4, 5, 6, 7, 8]

        motor = FakeDrumMotor(current_pocket=3)  # empty slot
        self._drain_and_verify(sorting, motor)

    def test_uneven_5_blue_3_pink(self):
        sorting = fill("blue", "blue", "blue", "blue", "blue",
                       "pink", "pink", "pink")
        assert sorted(sorting.blue_slots) == [0, 1, 2, 3, 4]
        assert sorted(sorting.pink_slots) == [6, 7, 8]

        motor = FakeDrumMotor(current_pocket=5)  # empty slot
        self._drain_and_verify(sorting, motor)

    def test_uneven_1_blue_7_pink(self):
        sorting = fill("blue", *(["pink"] * 7))
        motor = FakeDrumMotor(current_pocket=1)
        self._drain_and_verify(sorting, motor)

    def test_uneven_7_blue_1_pink(self):
        sorting = fill(*(["blue"] * 7), "pink")
        motor = FakeDrumMotor(current_pocket=7)
        self._drain_and_verify(sorting, motor)

    def test_single_blue_only(self):
        """Edge: one blue drum, no pink. Must still eject it."""
        sorting = fill("blue")
        motor = FakeDrumMotor(current_pocket=5)
        claimed, _, since = run_eject(sorting, motor)
        assert claimed == {0}
        assert_all_ejected(motor, claimed, since=since)

    def test_single_pink_only(self):
        sorting = fill("pink")
        motor = FakeDrumMotor(current_pocket=5)
        claimed, _, since = run_eject(sorting, motor)
        assert claimed == {0}  # pink first → near side (slot 0)
        assert_all_ejected(motor, claimed, since=since)

    def test_two_blue_two_pink(self):
        sorting = fill("blue", "blue", "pink", "pink")
        motor = FakeDrumMotor(current_pocket=0)
        self._drain_and_verify(sorting, motor)

    def test_all_eight_blue(self):
        """Worst case: every drum read as blue (total detection bias)."""
        sorting = fill(*(["blue"] * 8))
        assert sorted(sorting.blue_slots) == [0, 1, 2, 3, 4, 5, 6, 7]
        motor = FakeDrumMotor(current_pocket=8)
        claimed, _, since = run_eject(sorting, motor)
        assert claimed == {0, 1, 2, 3, 4, 5, 6, 7}
        assert_all_ejected(motor, claimed, since=since)

    def test_all_eight_pink(self):
        sorting = fill(*(["pink"] * 8))
        assert sorted(sorting.pink_slots) == [0, 1, 2, 3, 4, 5, 6, 7]
        motor = FakeDrumMotor(current_pocket=8)
        claimed, _, since = run_eject(sorting, motor)
        assert claimed == {0, 1, 2, 3, 4, 5, 6, 7}
        assert_all_ejected(motor, claimed, since=since)


# ── Starting from midpoint (mid-rotation interrupted) ──────────


class TestEjectFromMidpoint:
    def test_midpoint_retreats_first(self):
        sorting = perfect()
        motor = FakeDrumMotor(current_pocket=4, at_midpoint=True)
        claimed, _, since = run_eject(sorting, motor)
        assert not motor.at_midpoint, "Step must leave midpoint before ejecting"
        assert ("move_from_midpoint",) in motor.calls
        assert len(claimed) == 4
        assert_all_ejected(motor, claimed, since=since)


# ── No drums at all ─────────────────────────────────────────────


class TestNothingToEject:
    def test_empty_sort_state_is_noop(self):
        sorting = SortingService(MagicMock())
        sorting.info = lambda msg: None
        sorting.warn = lambda msg: None
        motor = FakeDrumMotor(current_pocket=0)
        run_eject(sorting, motor)
        assert motor.visited == [], "Must not rotate if there's nothing to eject"

    def test_after_both_colors_ejected_is_noop(self):
        sorting = perfect()
        motor = FakeDrumMotor(current_pocket=4)
        run_eject(sorting, motor)
        run_eject(sorting, motor)
        pre = len(motor.visited)
        run_eject(sorting, motor)
        assert len(motor.visited) == pre, "Third eject should be a no-op"


# ── Nearest-empty-slot / intake alignment ───────────────────────


class TestNearestEmptySlot:
    """go_to_empty_slot runs between drums; if it picks a wrong slot, the
    pusher opens above an occupied slot and drums fall out. Exhaustively
    verify the nearest-slot math across every occupancy + cursor combo."""

    def test_picks_nearest_on_ring(self):
        sorting = fill("blue", "pink", "blue", "pink")
        # slots: [b, b, None, None, None, None, None, p, p]
        assert sorting.slots == ["blue", "blue", None, None, None,
                                 None, None, "pink", "pink"]
        # current_pocket = 8 → nearest empty is slot 2? no, distance 6/3.
        # empties: [2,3,4,5,6]. ring_dist(8,2)=3, (8,3)=4, (8,4)=4,
        # (8,5)=3, (8,6)=2. Best = 6.
        assert sorting.nearest_empty_slot(8) == 6

    def test_nearest_empty_wraps_short(self):
        sorting = fill("blue", "blue", "blue", "blue", "pink", "pink",
                       "pink", "pink")
        # empties: [4]. Only one choice regardless of cursor.
        assert sorting.nearest_empty_slot(0) == 4
        assert sorting.nearest_empty_slot(4) == 4
        assert sorting.nearest_empty_slot(8) == 4

    def test_nearest_empty_raises_when_full(self):
        sorting = fill(*(["blue", "pink"] * 4), "blue")
        assert sorting.slots.count(None) == 0
        with pytest.raises(RuntimeError, match="No empty slots"):
            sorting.nearest_empty_slot(4)

    def test_go_to_empty_step_moves_to_correct_slot(self):
        """The step must move the motor to whichever slot is reported
        empty, not some pre-baked constant."""
        sorting = fill("blue", "pink", "blue")  # empties 3..7
        motor = FakeDrumMotor(current_pocket=5)
        robot = make_robot(sorting, motor)
        step = GoToEmptySlotStep()
        step.info = lambda msg: None
        step.warn = lambda msg: None
        run(step._execute_step(robot))
        assert motor.current_pocket == sorting.nearest_empty_slot(5)


# ── SortIntoSlotStep: wrong / missing detection ─────────────────


class _FakeColorService:
    """Minimal color-detection stub returning a queued sequence."""

    def __init__(self, returns: list[str | None]):
        self._returns = list(returns)

    async def detect_color(self) -> str | None:
        if not self._returns:
            return None
        return self._returns.pop(0)

    def reset(self) -> None:
        pass


def _patch_sort_step(step, color_service, sorting, motor):
    """Run a SortIntoSlotStep with injected services."""
    from src.service.color_detection_service import ColorDetectionService
    from src.service.drum_motor_service import DrumMotorService

    robot = MagicMock()

    def get_service(kind):
        if kind is ColorDetectionService:
            return color_service
        if kind is SortingService:
            return sorting
        if kind is DrumMotorService:
            return motor
        raise KeyError(kind)

    robot.get_service.side_effect = get_service
    return run(step._execute_step(robot))


class TestSortIntoSlotFallback:
    """When color detection fails, the step must still assign a slot and
    physically rotate there. A silent no-op would leave the revolver
    out of phase and corrupt the rest of the run."""

    def test_failed_detection_falls_back_to_guess(self):
        sorting = SortingService(MagicMock())
        sorting.info = lambda msg: None
        sorting.warn = lambda msg: None
        motor = FakeDrumMotor(current_pocket=0)
        step = SortIntoSlotStep()
        step.info = lambda msg: None
        step.warn = lambda msg: None
        color_service = _FakeColorService([None])  # detection fails

        _patch_sort_step(step, color_service, sorting, motor)

        # The step MUST have written a slot assignment and rotated.
        assigned = [i for i, c in enumerate(sorting.slots) if c is not None]
        assert len(assigned) == 1, (
            f"Fallback must still occupy exactly one slot, got {sorting.slots}"
        )
        target = assigned[0]
        assert motor.current_pocket == target, (
            "Motor did not rotate to the assigned slot after the fallback "
            f"guess (slot={target}, motor={motor.current_pocket})"
        )

    def test_eight_drums_each_misdetected_fills_all_slots(self):
        """Pathological case: every detection fails. After 8 drums the
        revolver should be full *in the logical model* so ejection has
        something to sweep. Guessing can pick either color but must never
        collide with itself."""
        sorting = SortingService(MagicMock())
        sorting.info = lambda msg: None
        sorting.warn = lambda msg: None
        motor = FakeDrumMotor(current_pocket=0)
        for _ in range(8):
            step = SortIntoSlotStep()
            step.info = lambda msg: None
            step.warn = lambda msg: None
            _patch_sort_step(step, _FakeColorService([None]),
                             sorting, motor)

        filled = [c for c in sorting.slots if c is not None]
        assert len(filled) == 8
        assert sorting.slots.count(None) == 1
        # And now ejection must still clear everything.
        run_eject(sorting, motor)
        run_eject(sorting, motor)
        assert sorting.slots == [None] * NUM_POCKETS


# ── Never eject the other color by accident ─────────────────────


class TestNoCrossContamination:
    """Ejecting blue must never sweep a pink slot across the hole, and
    vice versa. If the sweep loop overruns, a pink drum would be dropped
    in the blue destination — silent, hard-to-debug mission failure."""

    def test_first_eject_never_visits_other_color(self):
        """Whichever color is chosen first, the sweep must not rotate
        any slot of the *other* color under the ejection hole."""
        sorting = perfect()
        blue_slots = set(sorting.blue_slots)
        pink_slots = set(sorting.pink_slots)
        motor = FakeDrumMotor(current_pocket=4)

        claimed, color, since = run_eject(sorting, motor)
        visited = motor.visited[since:]
        other = pink_slots if color == "blue" else blue_slots
        overrun = [p for p in visited if p in other]
        assert not overrun, (
            f"Ejecting {color} rotated the wrong-color slots {overrun} "
            f"under the hole — a drum of the other color would drop "
            f"here. visited={visited}"
        )

    def test_second_eject_never_visits_phantom_first_color(self):
        """After color A is cleared, color B's sweep must stay inside
        B's slot range (A's pockets are now empty so transiting them
        is fine for correctness, but a good implementation should not
        rotate through more than it needs to)."""
        sorting = fill("pink", "pink", "pink", "pink")
        motor = FakeDrumMotor(current_pocket=5)
        claimed, color, since = run_eject(sorting, motor)
        assert color == "pink"
        visited = motor.visited[since:]
        # Pink first → slots 0-3. Sweep should not enter the empty far region.
        assert not (set(visited) & {5, 6, 7, 8}), (
            f"Pink sweep entered the empty far region: {visited}"
        )


# ── Monotonicity of slot assignment under missed intakes ────────


class TestSortingServiceEdge:
    def test_blue_pointer_never_regresses(self):
        s = fill("blue", "blue", "pink", "blue")
        assert s.blue_next == 3  # 0,1,2 used

    def test_pink_pointer_never_regresses(self):
        s = fill("pink", "pink", "blue", "pink")
        assert s.pink_next == 3  # 0,1,2 used (pink first → near side)

    def test_assign_after_full_raises_immediately(self):
        s = fill(*(["blue", "pink"] * 4), "blue")
        with pytest.raises(RuntimeError, match="Revolver full"):
            s.assign_slot("pink")
        with pytest.raises(RuntimeError, match="Revolver full"):
            s.assign_slot("blue")

    def test_guess_never_returns_exhausted_color(self):
        """Once all 4 of a color are accounted for, guess must not pick
        that color — otherwise assign_slot raises and sorting crashes
        mid-run."""
        import random
        random.seed(0)
        s = SortingService(MagicMock())
        s.info = lambda msg: None
        s.warn = lambda msg: None
        for _ in range(4):
            s.assign_slot("blue")
        # 4 blue locked in; 4 pink remaining. Guess must return "pink"
        # deterministically — otherwise we'd try to assign a 5th blue.
        for _ in range(50):
            assert s.guess_color() == "pink"

    def test_guess_never_returns_exhausted_pink(self):
        import random
        random.seed(0)
        s = SortingService(MagicMock())
        s.info = lambda msg: None
        s.warn = lambda msg: None
        for _ in range(4):
            s.assign_slot("pink")
        for _ in range(50):
            assert s.guess_color() == "blue"

    def test_eject_hole_slot_is_central(self):
        """The ejection hole is assumed to sit in the middle of the pink
        half so pink is always the shorter sweep. Several tests depend
        on this — pin it."""
        assert EJECT_HOLE_SLOT == 5
        assert NUM_POCKETS == 9
