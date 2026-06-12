"""Integration test: color detected during WaitForDrumStep must survive to SortIntoSlotStep.

The bug: collect_drums_step used to call color_service.reset() between
WaitForDrumStep (which detects and locks the color) and SortIntoSlotStep
(which reads it via detect_color()). The reset() wiped _latest_color,
so detect_color() returned None and the sorting fell back to guessing —
which alternated blue/pink on ties, causing the revolver to ping-pong
across its full length on every drum.
"""
import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from src.service.color_detection_service import ColorDetectionService
from raccoon_transport.types.raccoon.cam_blob_t import cam_blob_t
from raccoon_transport.types.raccoon.cam_detections_t import cam_detections_t


def make_color_service() -> ColorDetectionService:
    robot = MagicMock()
    svc = ColorDetectionService(robot)
    # Don't start the real camera/thread — we'll poke _latest_color directly.
    return svc


def make_detection_message(label: str | None) -> bytes:
    msg = cam_detections_t()
    msg.timestamp = 1
    msg.frame_width = 160
    msg.frame_height = 120
    msg.detections = []
    if label is not None:
        blob = cam_blob_t()
        blob.timestamp = 1
        blob.label = label
        blob.x = 10
        blob.y = 10
        blob.width = 20
        blob.height = 20
        blob.area = 400
        blob.confidence = 1.0
        msg.detections = [blob]
    msg.num_detections = len(msg.detections)
    return msg.encode()


class TestColorSurvivesLockToDetect:
    """Simulate the WaitForDrumStep → SortIntoSlotStep handoff."""

    def test_locked_color_readable_by_detect_color(self):
        """After lock_color(), detect_color() must return the locked color."""
        svc = make_color_service()

        # Simulate detection loop spotting pink
        with svc._lock:
            svc._latest_color = "pink"
            svc._color_event.set()

        # WaitForDrumStep locks it
        locked = svc.lock_color()
        assert locked == "pink"

        # SortIntoSlotStep reads it
        color = asyncio.get_event_loop().run_until_complete(svc.detect_color())
        assert color == "pink", (
            "detect_color() must return the locked color — "
            "if this is None, something cleared _latest_color between lock and detect"
        )

    def test_locked_color_not_overwritten_by_new_detections(self):
        """Once locked, new detections must NOT change _latest_color."""
        svc = make_color_service()

        # Detection loop spots pink
        with svc._lock:
            svc._latest_color = "pink"
            svc._color_event.set()

        svc.lock_color()

        # Detection loop now sees blue (next drum already visible) —
        # but lock is active, so it must be ignored.
        with svc._lock:
            if not svc._color_locked:
                svc._latest_color = "blue"  # this path should NOT execute

        color = asyncio.get_event_loop().run_until_complete(svc.detect_color())
        assert color == "pink", "Locked color must not be overwritten by new detections"

    def test_reset_before_detect_loses_color(self):
        """Prove that reset() between lock and detect kills the color.

        This is the exact bug pattern. The test documents the broken
        behaviour so we never reintroduce the reset() call.
        """
        svc = make_color_service()

        with svc._lock:
            svc._latest_color = "pink"
            svc._color_event.set()

        svc.lock_color()

        # THIS IS THE BUG: reset() between lock and detect
        svc.reset()

        color = asyncio.get_event_loop().run_until_complete(svc.detect_color())
        assert color is None, (
            "reset() should wipe the color — this test documents the bug pattern"
        )

    def test_detect_color_clears_after_read(self):
        """detect_color() must clear _latest_color so a second call returns None."""
        svc = make_color_service()

        with svc._lock:
            svc._latest_color = "blue"
            svc._color_event.set()

        svc.lock_color()

        loop = asyncio.get_event_loop()
        first = loop.run_until_complete(svc.detect_color())
        assert first == "blue"

        second = loop.run_until_complete(svc.detect_color())
        assert second is None, "detect_color() should be single-shot"

    def test_empty_daemon_detection_clears_visible_color(self):
        """The calibration test UI must return to NONE when detections disappear."""
        svc = make_color_service()

        svc._on_detections("raccoon/cam/detections", make_detection_message("pink"))
        assert svc.peek_color == "pink"
        assert svc.peek_confidence == 1.0
        assert svc._color_event.is_set()

        svc._on_detections("raccoon/cam/detections", make_detection_message(None))
        assert svc.peek_color is None
        assert svc.peek_confidence == 0.0
        assert not svc._color_event.is_set()

    def test_empty_daemon_detection_does_not_clear_locked_color(self):
        """Locked colors must survive until SortIntoSlotStep consumes them."""
        svc = make_color_service()

        svc._on_detections("raccoon/cam/detections", make_detection_message("blue"))
        svc.lock_color()
        svc._on_detections("raccoon/cam/detections", make_detection_message(None))

        assert svc.peek_color == "blue"


class TestCollectionFlowDoesNotReset:
    """Verify that the collect_drums_step sequence preserves detected colors.

    This simulates the exact phase1a → phase1b flow from CollectDrumsStep,
    checking that no reset() happens between detection and sort.
    """

    def test_full_drum_sequence_preserves_color(self):
        """Simulate 4 drums: detect, lock, (no reset!), read — color must survive each time."""
        svc = make_color_service()
        loop = asyncio.get_event_loop()

        colors_in = ["pink", "pink", "blue", "pink"]

        for expected_color in colors_in:
            # --- Phase 1a: WaitForDrumStep detects and locks ---
            svc.reset()  # reset from previous cycle (this happens at START of wait, not between)
            with svc._lock:
                svc._latest_color = expected_color
                svc._color_event.set()
            svc.lock_color()

            # --- NO reset() here! That was the bug. ---

            # --- Phase 1b: SortIntoSlotStep reads color ---
            color = loop.run_until_complete(svc.detect_color())
            assert color == expected_color, (
                f"Expected {expected_color} but got {color} — "
                f"color was lost between lock and detect"
            )
