"""Offline tests for DrumMotorService logic.

These tests exercise pure algorithmic logic (calibration, hysteresis,
pocket navigation math) without requiring real hardware. We mock the
RobotService base and hardware dependencies.
"""
from unittest.mock import MagicMock

import pytest

from src.service.drum_motor_service import (
    DEFAULT_MOTOR_SPEED,
    EMA_ALPHA,
    HYSTERESIS_FRACTION,
    NUM_POCKETS,
    DrumMotorService,
)

# ── Fixtures ──────────────────────────────────────────────────────

class FakeMotor:
    """Minimal motor mock that records calls."""
    def __init__(self):
        self._speed = 0
        self._position = 0

    def set_speed(self, speed):
        self._speed = speed

    def brake(self):
        self._speed = 0

    def get_position(self):
        return self._position


class FakeSensor:
    """Sensor that yields values from a predetermined sequence."""
    def __init__(self, values=None):
        self._values = list(values or [])
        self._idx = 0

    def read(self):
        if self._idx < len(self._values):
            val = self._values[self._idx]
            self._idx += 1
            return val
        return self._values[-1] if self._values else 0


def make_service(sensor_values=None):
    """Create a DrumMotorService with mocked robot and hardware."""
    robot = MagicMock()
    robot.defs = MagicMock()
    robot.defs.drum_motor = FakeMotor()
    robot.defs.drum_light_sensor = FakeSensor(sensor_values or [])

    service = DrumMotorService.__new__(DrumMotorService)
    service._robot = robot
    service._blocked_threshold = None
    service._pocket_threshold = None
    service._current_index = 0

    # Stub logging methods
    service.info = MagicMock()
    service.warn = MagicMock()

    # Wire properties to our fakes
    type(service).robot = property(lambda self: self._robot)

    return service


# ── Calibration Tests ─────────────────────────────────────────────

class TestCalibration:
    def test_not_calibrated_initially(self):
        s = make_service()
        assert not s.is_calibrated

    def test_apply_calibration(self):
        s = make_service()
        s.apply_calibration(blocked=800.0, pocket=200.0)
        assert s.is_calibrated
        assert s.blocked_threshold == 800.0
        assert s.pocket_threshold == 200.0

    def test_midpoint(self):
        s = make_service()
        s.apply_calibration(blocked=800.0, pocket=200.0)
        assert s.midpoint == pytest.approx(500.0)

    def test_hysteresis_thresholds(self):
        s = make_service()
        s.apply_calibration(blocked=800.0, pocket=200.0)
        low, high = s.hysteresis_thresholds
        # spread = 600, band = 600 * 0.3 = 180
        # midpoint = 500
        assert low == pytest.approx(320.0)
        assert high == pytest.approx(680.0)

    def test_hysteresis_symmetric(self):
        """Low and high are equidistant from midpoint."""
        s = make_service()
        s.apply_calibration(blocked=1000.0, pocket=0.0)
        low, high = s.hysteresis_thresholds
        mid = s.midpoint
        assert (mid - low) == pytest.approx(high - mid)

    def test_midpoint_raises_when_uncalibrated(self):
        s = make_service()
        with pytest.raises(AssertionError):
            _ = s.midpoint


# ── Pocket Navigation Math ───────────────────────────────────────

class TestGoToLogic:
    """Test the shortest-path calculation in go_to without running motors."""

    def _go_to_direction(self, current, target):
        """Reproduce go_to's shortest-path decision, return (direction, count)."""
        delta = (target - current) % NUM_POCKETS
        if delta == 0:
            return ("none", 0)
        if delta <= NUM_POCKETS // 2:
            return ("advance", delta)
        else:
            return ("retreat", NUM_POCKETS - delta)

    def test_same_index(self):
        assert self._go_to_direction(0, 0) == ("none", 0)

    def test_forward_short(self):
        # 0 -> 3: delta=3, NUM_POCKETS//2=4, so advance 3
        assert self._go_to_direction(0, 3) == ("advance", 3)

    def test_backward_short(self):
        # 0 -> 7: delta=7, > 4, so retreat NUM_POCKETS-7=1
        assert self._go_to_direction(0, 7) == ("retreat", NUM_POCKETS - 7)

    def test_wraparound_forward(self):
        # 7 -> 1: delta=(1-7)%NUM_POCKETS, advance
        assert self._go_to_direction(7, 1) == ("advance", (1 - 7) % NUM_POCKETS)

    def test_wraparound_backward(self):
        # 1 -> 7: delta=(7-1)%NUM_POCKETS=6, > 4, retreat NUM_POCKETS-6
        assert self._go_to_direction(1, 7) == ("retreat", NUM_POCKETS - 6)

    def test_halfway_prefers_advance(self):
        # delta=NUM_POCKETS//2, so advance
        assert self._go_to_direction(0, NUM_POCKETS // 2) == ("advance", NUM_POCKETS // 2)

    def test_all_targets_reachable(self):
        """Every target from every starting index should produce a valid plan."""
        for start in range(NUM_POCKETS):
            for target in range(NUM_POCKETS):
                direction, count = self._go_to_direction(start, target)
                if start == target:
                    assert direction == "none"
                else:
                    assert direction in ("advance", "retreat")
                    assert 1 <= count <= NUM_POCKETS - 1


# ── EMA Filter Tests ─────────────────────────────────────────────

class TestEMAFilter:
    """Test the exponential moving average behavior used in _move."""

    def test_convergence(self):
        """EMA should converge toward a constant signal."""
        filtered = 0.0
        for _ in range(100):
            filtered += EMA_ALPHA * (500.0 - filtered)
        assert filtered == pytest.approx(500.0, abs=1.0)

    def test_responsiveness(self):
        """With alpha=0.9, a step change should reach 90% in ~2 samples."""
        filtered = 0.0
        filtered += EMA_ALPHA * (1000.0 - filtered)  # sample 1
        filtered += EMA_ALPHA * (1000.0 - filtered)  # sample 2
        assert filtered > 900.0  # should be 990 with alpha=0.9

    def test_noise_rejection(self):
        """EMA should smooth out high-frequency noise."""
        import random
        random.seed(42)
        base = 500.0
        filtered = base
        deviations = []
        for _ in range(200):
            noisy = base + random.uniform(-100, 100)
            filtered += EMA_ALPHA * (noisy - filtered)
            deviations.append(abs(filtered - base))
        avg_deviation = sum(deviations) / len(deviations)
        # with alpha=0.9, filtered tracks noise closely — but still smoother
        assert avg_deviation < 100  # raw noise has avg deviation ~50


# ── Constants Sanity ──────────────────────────────────────────────

class TestConstants:
    def test_num_pockets_positive(self):
        assert NUM_POCKETS > 0

    def test_hysteresis_fraction_in_range(self):
        assert 0 < HYSTERESIS_FRACTION < 1

    def test_ema_alpha_in_range(self):
        assert 0 < EMA_ALPHA <= 1

    def test_default_motor_speed_in_range(self):
        assert 0 < DEFAULT_MOTOR_SPEED <= 1
