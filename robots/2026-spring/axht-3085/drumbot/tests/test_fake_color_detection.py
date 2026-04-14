"""Tests for FakeColorDetectionService — verify it works as a drop-in
replacement for ColorDetectionService in the collect/sort/eject pipeline."""

import asyncio
from unittest.mock import MagicMock

import pytest

from src.service.color_detection_service import ColorDetectionService
from src.service.fake_color_detection_service import (
    FakeColorDetectionService,
    install_fake_color_service,
)
from src.service.sorting_service import SortingService


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def make_fake(sequence=None) -> FakeColorDetectionService:
    robot = MagicMock()
    return FakeColorDetectionService(robot, sequence=sequence)


class TestFakeDetectionCycle:
    """The fake must follow the same reset → wait → lock → detect flow
    that WaitForDrumStep and SortIntoSlotStep use."""

    def test_alternating_sequence(self):
        svc = make_fake(["blue", "pink", "blue", "pink"])
        colors = []
        for _ in range(4):
            svc.reset()
            run(svc.wait_for_color(1.0))
            svc.lock_color()
            colors.append(run(svc.detect_color()))
        assert colors == ["blue", "pink", "blue", "pink"]

    def test_default_sequence_is_alternating(self):
        svc = make_fake()
        colors = []
        for _ in range(8):
            svc.reset()
            run(svc.wait_for_color(1.0))
            svc.lock_color()
            colors.append(run(svc.detect_color()))
        assert colors == ["blue", "pink"] * 4

    def test_lock_prevents_overwrite(self):
        svc = make_fake(["blue", "pink"])
        svc.reset()
        run(svc.wait_for_color(1.0))  # sets "blue"
        svc.lock_color()
        # Another wait should not overwrite the locked color
        run(svc.wait_for_color(1.0))
        assert run(svc.detect_color()) == "blue"

    def test_reset_clears_state(self):
        svc = make_fake(["blue"])
        svc.reset()
        run(svc.wait_for_color(1.0))
        svc.lock_color()
        svc.reset()
        # After reset, detect_color should return None (nothing locked)
        assert run(svc.detect_color()) is None

    def test_peek_color(self):
        svc = make_fake(["pink"])
        assert svc.peek_color is None
        svc.reset()
        run(svc.wait_for_color(1.0))
        assert svc.peek_color == "pink"

    def test_continuous_color_seconds(self):
        svc = make_fake(["blue"])
        assert svc.continuous_color_seconds is None
        svc.reset()
        run(svc.wait_for_color(1.0))
        assert svc.continuous_color_seconds is not None
        assert svc.continuous_color_seconds >= 0


class TestInstallHelper:
    """install_fake_color_service must make get_service(ColorDetectionService)
    return the fake."""

    def test_install_registers_under_real_class(self):
        robot = MagicMock()
        robot._services = {}
        fake = install_fake_color_service(robot, sequence=["pink", "blue"])
        assert robot._services[ColorDetectionService] is fake
        assert isinstance(fake, FakeColorDetectionService)


class TestFakeWithSortingPipeline:
    """End-to-end: use FakeColorDetectionService to feed SortIntoSlotStep
    and verify the sorting state ends up correct."""

    def test_eight_drums_sorted_correctly(self):
        from src.service.drum_motor_service import DrumMotorService
        from src.steps.drum_collector.sort_into_slot_step import SortIntoSlotStep
        from tests.test_eject_edge_cases import FakeDrumMotor

        fake_color = make_fake()  # alternating blue, pink
        sorting = SortingService(MagicMock())
        sorting.info = lambda msg: None
        sorting.warn = lambda msg: None
        motor = FakeDrumMotor(current_pocket=0)

        robot = MagicMock()

        def get_service(cls):
            if cls is ColorDetectionService:
                return fake_color
            if cls is SortingService:
                return sorting
            if cls is DrumMotorService:
                return motor
            raise KeyError(cls)

        robot.get_service.side_effect = get_service

        for _ in range(8):
            # Simulate WaitForDrumStep
            fake_color.reset()
            run(fake_color.wait_for_color(1.0))
            fake_color.lock_color()

            # Simulate SortIntoSlotStep
            step = SortIntoSlotStep()
            step.info = lambda msg: None
            step.warn = lambda msg: None
            run(step._execute_step(robot))

        # With alternating blue/pink from pocket 0:
        # blue goes to lo side (0,1,2,3), pink goes to hi side (8,7,6,5)
        assert sorting.slots.count("blue") == 4
        assert sorting.slots.count("pink") == 4
        assert sorting.slots.count(None) == 1
        assert sorting.slots[4] is None  # gap in the middle
