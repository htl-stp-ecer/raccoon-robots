"""Offline tests for SortingService — bidirectional revolver sorting."""
from unittest.mock import MagicMock

import pytest

from src.service.sorting_service import NUM_SLOTS, SortingService


def make_service():
    robot = MagicMock()
    service = SortingService(robot)
    return service


class TestAssignSlot:
    def test_first_blue_goes_to_slot_0(self):
        s = make_service()
        assert s.assign_slot("blue") == 0

    def test_first_pink_goes_to_slot_0(self):
        """First-seen color always gets the near side (slot 0)."""
        s = make_service()
        assert s.assign_slot("pink") == 0

    def test_alternating_worst_case(self):
        """B-P-B-P-B-P-B-P → blue in 0-3, pink in 7-4."""
        s = make_service()
        colors = ["blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink"]
        expected = [0, 7, 1, 6, 2, 5, 3, 4]
        for color, exp in zip(colors, expected):
            assert s.assign_slot(color) == exp
        assert s.slots == ["blue", "blue", "blue", "blue", "pink", "pink", "pink", "pink"]

    def test_alternating_pink_first(self):
        """P-B-P-B-P-B-P-B → pink in 0-3, blue in 7-4."""
        s = make_service()
        colors = ["pink", "blue", "pink", "blue", "pink", "blue", "pink", "blue"]
        expected = [0, 7, 1, 6, 2, 5, 3, 4]
        for color, exp in zip(colors, expected):
            assert s.assign_slot(color) == exp
        assert s.slots == ["pink", "pink", "pink", "pink", "blue", "blue", "blue", "blue"]

    def test_all_blue(self):
        s = make_service()
        for i in range(NUM_SLOTS):
            assert s.assign_slot("blue") == i
        assert s.slots == ["blue"] * NUM_SLOTS

    def test_all_pink(self):
        """Pink first → pink gets near side (0→7)."""
        s = make_service()
        for i in range(NUM_SLOTS):
            assert s.assign_slot("pink") == i
        assert s.slots == ["pink"] * NUM_SLOTS

    def test_uneven_5_blue_3_pink(self):
        s = make_service()
        for _ in range(5):
            s.assign_slot("blue")
        for _ in range(3):
            s.assign_slot("pink")
        assert s.slots == ["blue", "blue", "blue", "blue", "blue", "pink", "pink", "pink"]

    def test_overflow_raises(self):
        """8 drums fill all slots; the 9th must raise."""
        s = make_service()
        for _ in range(4):
            s.assign_slot("blue")
            s.assign_slot("pink")
        assert s.slots.count(None) == 0
        with pytest.raises(RuntimeError, match="Revolver full"):
            s.assign_slot("pink")

    def test_unknown_color_raises(self):
        s = make_service()
        with pytest.raises(ValueError, match="Unknown color"):
            s.assign_slot("green")


class TestSlotQueries:
    def test_blue_slots_ascending(self):
        s = make_service()
        s.assign_slot("blue")
        s.assign_slot("pink")
        s.assign_slot("blue")
        assert s.blue_slots == [0, 1]

    def test_pink_slots_descending(self):
        """Pink first → near side. P→0, B→7, P→1."""
        s = make_service()
        s.assign_slot("pink")
        s.assign_slot("blue")
        s.assign_slot("pink")
        assert s.pink_slots == [1, 0]


class TestRotationWorstCase:
    """Verify the worst-case rotation analysis from the spec."""

    def test_max_rotation_is_4(self):
        """Alternating B-P-B-P-B-P-B-P: max single rotation should be 4 slots."""
        s = make_service()
        colors = ["blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink"]
        current = 0
        max_rotation = 0

        for color in colors:
            target = s.assign_slot(color)
            # shortest path on ring of NUM_SLOTS
            diff = (target - current) % NUM_SLOTS
            if diff > NUM_SLOTS // 2:
                diff = NUM_SLOTS - diff
            max_rotation = max(max_rotation, diff)
            current = target

        assert max_rotation == 4

    def test_same_color_always_1_slot(self):
        """Consecutive same-color drums should always be 1 slot apart."""
        s = make_service()
        current = 0
        for _ in range(NUM_SLOTS):
            target = s.assign_slot("blue")
            diff = (target - current) % NUM_SLOTS
            if diff > NUM_SLOTS // 2:
                diff = NUM_SLOTS - diff
            assert diff <= 1
            current = target
