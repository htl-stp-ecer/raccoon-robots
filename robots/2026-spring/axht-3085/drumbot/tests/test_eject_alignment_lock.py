"""Regression guard for the "eject started from the wrong pocket" bug.

Reproduces the run where a camera-stuck emergency fired at the end of
collection: the safe-mode nav-lock (`motor_locked`) made `go_to_pocket`
early-return, so the pre-eject `go_to_slot(2)` alignment never ran. The
revolver stayed where the emergency left it and the eject swept from a
2-pocket offset — nothing landed on the pipe.

The fix: `after_collect` calls `begin_eject()` before the slot-2 alignment
when collection failed, so the alignment gets at least one real attempt
(the retry budget, not a hard lock, protects a genuinely faulted motor).

These tests pin the underlying service invariant that fix relies on.
"""

from unittest.mock import MagicMock

import pytest

from src.service.drum_motor_service import DrumMotorService


def make_service() -> DrumMotorService:
    svc = DrumMotorService(MagicMock())
    svc._current_pocket = 4  # where the stuck emergency left the revolver
    return svc


def test_non_motor_emergency_locks_navigation():
    """A camera/timing emergency (collection_failed, motor NOT faulted)
    initially suppresses all revolver navigation."""
    svc = make_service()
    svc.collection_failed = True
    svc.motor_faulted = False

    assert svc.motor_locked is True


@pytest.mark.asyncio
async def test_go_to_pocket_skips_instantly_while_locked():
    """While locked, go_to_pocket must not move — it returns 'none' before
    touching the motor. This is exactly the instant-skip that stranded the
    slot-2 alignment in the real run."""
    svc = make_service()
    svc.collection_failed = True
    motor = svc.motor  # robot is a MagicMock → stable child mock for the drum motor

    result = await svc.go_to_pocket(2)

    assert result == "none"
    assert svc.current_pocket == 4  # never rotated
    motor.set_velocity.assert_not_called()  # guard returned before touching the motor


def test_begin_eject_drops_lock_for_non_motor_emergency():
    """begin_eject must release the lock so the slot-2 alignment is attempted
    at least once, even though collection_failed is still set."""
    svc = make_service()
    svc.collection_failed = True
    svc.motor_faulted = False

    svc.begin_eject()

    assert svc.eject_mode is True
    assert svc.motor_locked is False  # go_to_pocket will now actually try


def test_begin_eject_uses_single_attempt_for_faulted_motor():
    """A genuinely faulted motor still gets exactly one careful attempt
    (no retry) rather than being driven repeatedly."""
    svc = make_service()
    svc.collection_failed = True
    svc.motor_faulted = True

    svc.begin_eject()

    assert svc.motor_locked is False  # lock dropped → move is attempted
    assert svc.stall_retries == 1     # ...but only once
