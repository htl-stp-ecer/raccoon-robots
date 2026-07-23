"""Tests for the pre-pusher-open rotation logic.

Before opening the drum pusher servo for the next drum, the revolver
must be positioned over an empty pocket — otherwise the loading hole
exposes the just-sorted drum and it falls back out.

Covers:
  - SortingService.nearest_empty_pocket (selection logic)
  - RotateToNextEmptyPocketStep (drives drum_service.go_to_pocket)
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from src.service.drum_motor_service import NUM_POCKETS
from src.service.sorting_service import NUM_SLOTS, SortingService
from src.steps.drum_collector.sort_into_slot_step import (
    RotateToNextEmptyPocketStep,
)


def _silent(service):
    service.info = lambda msg: None
    service.warn = lambda msg: None
    return service


def _service(slots: list[str | None] | None = None) -> SortingService:
    s = _silent(SortingService(MagicMock()))
    if slots is not None:
        assert len(slots) == NUM_SLOTS
        s.slots = list(slots)
    return s


# ── SortingService.nearest_empty_pocket ─────────────────────────────


class TestNearestEmptyPocket:
    def test_all_empty_returns_current(self):
        s = _service()
        assert s.nearest_empty_pocket(0) == 0
        assert s.nearest_empty_pocket(3) == 3

    def test_all_full_returns_none(self):
        s = _service(["blue"] * NUM_SLOTS)
        assert s.nearest_empty_pocket(0) is None

    def test_current_pocket_filled_picks_nearest(self):
        # Slot 0 filled, current=0 — neighbours 1 and 7 are equidistant.
        # Tie-break is forward → 1.
        s = _service(["blue", None, None, None, None, None, None, None])
        assert s.nearest_empty_pocket(0) == 1

    def test_forward_tiebreak(self):
        # current=4, slots 3 and 5 both empty (dist 1) → prefer forward = 5.
        s = _service([None] * NUM_SLOTS)
        s.slots[4] = "blue"
        assert s.nearest_empty_pocket(4) == 5

    def test_picks_backward_when_closer(self):
        # current=2, slots 3,4,5 filled — slot 1 (dist 1) closer than slot 6 (dist 4).
        s = _service([None, None, "blue", "blue", "blue", "blue", None, None])
        assert s.nearest_empty_pocket(2) == 1

    def test_ring_wraps(self):
        # current=0, slots 0..6 filled, only slot 7 empty → distance 1 backward.
        s = _service(["blue"] * 7 + [None])
        assert s.nearest_empty_pocket(0) == 7

    def test_skips_over_filled_to_find_empty(self):
        # current=0, slot 0 filled, slot 1 filled → empty is 2 (fwd 2) or 7 (bwd 1).
        # 7 is closer → pick 7.
        s = _service(["blue", "blue", None, None, None, None, None, None])
        assert s.nearest_empty_pocket(0) == 7


# ── RotateToNextEmptyPocketStep ─────────────────────────────────────


class FakeDrumMotor:
    """Minimal drum-motor fake recording go_to_pocket calls."""

    def __init__(self, current_pocket: int = 0) -> None:
        self.current_pocket = current_pocket
        self.calls: list[tuple] = []

    async def go_to_pocket(
        self, pocket: int, *, precise: bool = False, occupied=None
    ) -> str:
        self.calls.append((pocket, precise, frozenset(occupied or ())))
        self.current_pocket = pocket % NUM_POCKETS
        return "forward"

    def info(self, msg: str) -> None:
        pass

    def warn(self, msg: str) -> None:
        pass


def _robot(sorting: SortingService, motor: FakeDrumMotor) -> MagicMock:
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


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _run_step(sorting: SortingService, motor: FakeDrumMotor) -> None:
    step = RotateToNextEmptyPocketStep()
    step.info = lambda msg: None
    step.warn = lambda msg: None
    _run(step._execute_step(_robot(sorting, motor)))


class TestRotateToNextEmptyPocketStep:
    def test_first_drum_no_rotation(self):
        """Slot 0 empty, current=0 — no motor move."""
        sorting = _service()
        motor = FakeDrumMotor(current_pocket=0)
        _run_step(sorting, motor)
        assert motor.calls == []
        assert motor.current_pocket == 0

    def test_rotates_off_filled_pocket(self):
        """After sorting drum 1 into slot 0, current_pocket=0 is filled —
        rotate to nearest empty pocket before next pusher.open()."""
        sorting = _service(["blue", None, None, None, None, None, None, None])
        motor = FakeDrumMotor(current_pocket=0)
        _run_step(sorting, motor)
        assert len(motor.calls) == 1
        target, precise, occupied = motor.calls[0]
        assert target == 1
        assert precise is False
        assert occupied == frozenset({0})

    def test_passes_all_occupied_to_router(self):
        """go_to_pocket must receive every filled slot so it can avoid
        exposing them to the loading hole during transit."""
        sorting = _service(["blue", "pink", None, None, None, None, None, "blue"])
        motor = FakeDrumMotor(current_pocket=0)
        _run_step(sorting, motor)
        assert len(motor.calls) == 1
        _target, _precise, occupied = motor.calls[0]
        assert occupied == frozenset({0, 1, 7})

    def test_already_on_empty_pocket_noop(self):
        """If current pocket is empty (e.g. after pre-rotation), skip."""
        sorting = _service(["blue", None, None, None, None, None, None, None])
        motor = FakeDrumMotor(current_pocket=1)  # already on empty slot 1
        _run_step(sorting, motor)
        assert motor.calls == []

    def test_revolver_full_logs_and_skips(self):
        """All slots full → nothing to do; must not raise."""
        sorting = _service(["blue"] * NUM_SLOTS)
        motor = FakeDrumMotor(current_pocket=3)
        _run_step(sorting, motor)
        assert motor.calls == []
        assert motor.current_pocket == 3
