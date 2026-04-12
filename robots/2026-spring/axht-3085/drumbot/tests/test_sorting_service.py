"""Offline tests for SortingService — bidirectional revolver sorting."""
from unittest.mock import MagicMock

import pytest

from src.service.sorting_service import NUM_SLOTS, SortingService


def make_service():
    robot = MagicMock()
    service = SortingService(robot)
    return service


class TestAssignSlot:
    def test_first_blue_goes_to_slot_1(self):
        s = make_service()
        assert s.assign_slot("blue") == 1

    def test_first_pink_goes_to_slot_1(self):
        """First drum always gets the near side (slot 1, CW)."""
        s = make_service()
        assert s.assign_slot("pink") == 1

    def test_alternating_blue_first(self):
        """B-P-B-P-B-P-B-P → blue CW (1-4), pink CCW (8-5)."""
        s = make_service()
        colors = ["blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink"]
        expected = [1, 8, 2, 7, 3, 6, 4, 5]
        for color, exp in zip(colors, expected):
            assert s.assign_slot(color) == exp
        assert s.slots == [None, "blue", "blue", "blue", "blue", "pink", "pink", "pink", "pink"]

    def test_alternating_pink_first(self):
        """P-B-P-B-P-B-P-B → pink CW (1-4), blue CCW (8-5)."""
        s = make_service()
        colors = ["pink", "blue", "pink", "blue", "pink", "blue", "pink", "blue"]
        expected = [1, 8, 2, 7, 3, 6, 4, 5]
        for color, exp in zip(colors, expected):
            assert s.assign_slot(color) == exp
        assert s.slots == [None, "pink", "pink", "pink", "pink", "blue", "blue", "blue", "blue"]

    def test_all_blue(self):
        s = make_service()
        for i in range(8):
            assert s.assign_slot("blue") == i + 1
        assert s.slots == [None] + ["blue"] * 8

    def test_all_pink(self):
        s = make_service()
        for i in range(8):
            assert s.assign_slot("pink") == i + 1
        assert s.slots == [None] + ["pink"] * 8

    def test_uneven_5_blue_3_pink(self):
        s = make_service()
        for _ in range(5):
            s.assign_slot("blue")
        for _ in range(3):
            s.assign_slot("pink")
        assert s.slots == [None, "blue", "blue", "blue", "blue", "blue", "pink", "pink", "pink"]

    def test_overflow_raises(self):
        """8 drums fill all usable slots (1-8); the 9th must raise."""
        s = make_service()
        for _ in range(4):
            s.assign_slot("blue")
            s.assign_slot("pink")
        # 8 drums fill slots 1-8; slot 0 stays empty
        assert s.slots.count(None) == 1
        assert s.slots[0] is None
        # 9th drum has no room
        with pytest.raises(RuntimeError, match="Revolver full"):
            s.assign_slot("blue")

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
        assert s.blue_slots == [1, 2]

    def test_pink_slots_descending(self):
        """Pink first → CW side. P→1, B→8, P→2. Pink slots: [2, 1] (descending iter)."""
        s = make_service()
        s.assign_slot("pink")
        s.assign_slot("blue")
        s.assign_slot("pink")
        assert s.pink_slots == [2, 1]

    def test_empty_slot_after_full(self):
        s = make_service()
        colors = ["blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink"]
        for c in colors:
            s.assign_slot(c)
        assert s.empty_slot == 0

    def test_empty_slot_not_full_returns_none(self):
        s = make_service()
        s.assign_slot("blue")
        assert s.empty_slot is None  # multiple empties


class TestRotationWorstCase:
    """Verify the worst-case rotation analysis from the spec."""

    def test_max_shortest_path_is_4(self):
        """Alternating B-P-B-P-B-P-B-P: max single shortest-path rotation should be 4 slots."""
        s = make_service()
        colors = ["blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink"]
        current = 0
        max_rotation = 0

        for color in colors:
            target = s.assign_slot(color)
            # shortest path on ring of 9
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
        for _ in range(8):
            target = s.assign_slot("blue")
            diff = (target - current) % NUM_SLOTS
            if diff > NUM_SLOTS // 2:
                diff = NUM_SLOTS - diff
            assert diff <= 1
            current = target
