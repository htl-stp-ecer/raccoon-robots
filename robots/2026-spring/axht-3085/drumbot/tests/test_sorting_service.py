"""Offline tests for SortingService — bidirectional revolver sorting."""
import pytest
from unittest.mock import MagicMock

from src.service.sorting_service import SortingService, NUM_SLOTS


def make_service():
    robot = MagicMock()
    service = SortingService(robot)
    return service


class TestAssignSlot:
    def test_first_blue_goes_to_slot_0(self):
        s = make_service()
        assert s.assign_slot("blue") == 0

    def test_first_pink_goes_to_slot_8(self):
        s = make_service()
        assert s.assign_slot("pink") == 8

    def test_alternating_worst_case(self):
        """B-P-B-P-B-P-B-P → blue in 0-3, pink in 8-5."""
        s = make_service()
        colors = ["blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink"]
        expected = [0, 8, 1, 7, 2, 6, 3, 5]
        for color, exp in zip(colors, expected):
            assert s.assign_slot(color) == exp
        assert s.slots == ["blue", "blue", "blue", "blue", None, "pink", "pink", "pink", "pink"]

    def test_all_blue(self):
        s = make_service()
        for i in range(8):
            assert s.assign_slot("blue") == i
        assert s.slots == ["blue"] * 8 + [None]

    def test_all_pink(self):
        s = make_service()
        for i in range(8):
            assert s.assign_slot("pink") == 8 - i
        assert s.slots == [None] + ["pink"] * 8

    def test_uneven_5_blue_3_pink(self):
        s = make_service()
        for _ in range(5):
            s.assign_slot("blue")
        for _ in range(3):
            s.assign_slot("pink")
        assert s.slots == ["blue", "blue", "blue", "blue", "blue", None, "pink", "pink", "pink"]

    def test_overflow_raises(self):
        """9 drums fill all slots; the 10th must raise."""
        s = make_service()
        for _ in range(4):
            s.assign_slot("blue")
            s.assign_slot("pink")
        # 9th drum fills the last slot (slot 4)
        s.assign_slot("blue")
        assert s.slots.count(None) == 0
        # 10th drum has no room
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
        s = make_service()
        s.assign_slot("pink")
        s.assign_slot("blue")
        s.assign_slot("pink")
        assert s.pink_slots == [8, 7]

    def test_empty_slot_after_full(self):
        s = make_service()
        colors = ["blue", "pink", "blue", "pink", "blue", "pink", "blue", "pink"]
        for c in colors:
            s.assign_slot(c)
        assert s.empty_slot == 4

    def test_empty_slot_not_full_returns_none(self):
        s = make_service()
        s.assign_slot("blue")
        assert s.empty_slot is None  # multiple empties


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
