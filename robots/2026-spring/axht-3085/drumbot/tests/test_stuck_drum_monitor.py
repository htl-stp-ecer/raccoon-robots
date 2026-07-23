"""Tests for the stuck-drum watchdog in CollectDrumsStep.

The monitor polls `color_service.continuous_color_seconds` every 100ms.
If a color stays continuously visible for > 1.5s, it enters safe mode:
    - drum_service.collection_failed = True
    - drum_service.stall_retries = 1
    - drum pusher servo forced open

These tests pin the threshold (strict `>`), the safe-mode side-effects,
and the integration with FakeColorDetectionService — so that a mutation
to the threshold, comparison operator, or any field assignment is caught.
"""

import asyncio
import sys
import types
from unittest.mock import MagicMock

import pytest

# Stub heavy UI screen modules before importing CollectDrumsStep — the real
# screen classes pull in UI decorators that aren't available offline.
for _modname in (
    "src.steps.drum_collector.screens",
    "src.steps.drum_collector.screens.drum_collection_screen",
    "src.steps.drum_collector.screens.emergency_screen",
):
    _mod = types.ModuleType(_modname)
    sys.modules[_modname] = _mod
sys.modules["src.steps.drum_collector.screens.drum_collection_screen"].DrumCollectionScreen = type(
    "DrumCollectionScreen", (), {"__init__": lambda self, *a, **kw: None}
)
sys.modules["src.steps.drum_collector.screens.emergency_screen"].EmergencyScreen = type(
    "EmergencyScreen", (), {"__init__": lambda self, *a, **kw: None}
)

# Stub heavy sibling step modules only if they aren't already real-importable.
# (Some of them work fine on their own; we only replace the ones that fail
# due to `from raccoon import *` not exposing Defer/seq/etc. through the
# conftest mock.)
def _stub_if_unimportable(modname: str, attrs: dict) -> None:
    if modname in sys.modules:
        return
    try:
        __import__(modname)
    except Exception:
        mod = types.ModuleType(modname)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[modname] = mod

_noop = lambda *a, **kw: None
_stub_if_unimportable("src.steps.drum_lifting_step", {
    "drum_align_on_back": _noop,
    "drum_lifting_down": _noop,
    "drum_lifting_up": _noop,
})
_stub_if_unimportable("src.steps.wait_for_drum_step", {"wait_for_drum": _noop})
_stub_if_unimportable("src.steps.drum_collector.sort_into_slot_step", {
    "advance_to_midpoint": _noop,
    "block_timer_check": _noop,
    "block_timer_start": _noop,
    "sort_into_slot": _noop,
})

from src.service.fake_color_detection_service import FakeColorDetectionService  # noqa: E402
from src.steps.collect_drums_step import CollectDrumsStep  # noqa: E402


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def make_step() -> CollectDrumsStep:
    step = CollectDrumsStep()
    step.info = lambda msg: None
    step.warn = lambda msg: None
    return step


def make_drum_service() -> MagicMock:
    drum = MagicMock()
    drum.collection_failed = False
    drum.stall_retries = 2
    return drum


class TestStuckMonitorThreshold:
    """The monitor uses a strict `>` against STUCK_THRESHOLD = 1.5s."""

    def test_triggers_safe_mode_above_threshold(self):
        step = make_step()
        color = MagicMock()
        color.continuous_color_seconds = 1.6
        drum = make_drum_service()

        async def _run():
            await asyncio.wait_for(
                step._stuck_drum_monitor(color, drum, MagicMock()),
                timeout=1.0,
            )

        run(_run())
        assert drum.collection_failed is True
        assert drum.stall_retries == 1

    def test_does_not_trigger_below_threshold(self):
        step = make_step()
        color = MagicMock()
        color.continuous_color_seconds = 1.4
        drum = make_drum_service()

        async def _run():
            await asyncio.wait_for(
                step._stuck_drum_monitor(color, drum, MagicMock()),
                timeout=0.35,  # ~3 monitor ticks
            )

        with pytest.raises(asyncio.TimeoutError):
            run(_run())
        assert drum.collection_failed is False
        assert drum.stall_retries == 2

    def test_does_not_trigger_at_exact_threshold(self):
        # Strict `>` — 1.5 exactly must NOT trip. Catches a `>=` mutation.
        step = make_step()
        color = MagicMock()
        color.continuous_color_seconds = 1.5
        drum = make_drum_service()

        async def _run():
            await asyncio.wait_for(
                step._stuck_drum_monitor(color, drum, MagicMock()),
                timeout=0.35,
            )

        with pytest.raises(asyncio.TimeoutError):
            run(_run())
        assert drum.collection_failed is False

    def test_does_not_trigger_when_continuous_seconds_is_none(self):
        # `None` (no color visible) must not be treated as "stuck".
        step = make_step()
        color = MagicMock()
        color.continuous_color_seconds = None
        drum = make_drum_service()

        async def _run():
            await asyncio.wait_for(
                step._stuck_drum_monitor(color, drum, MagicMock()),
                timeout=0.35,
            )

        with pytest.raises(asyncio.TimeoutError):
            run(_run())
        assert drum.collection_failed is False


class TestStuckMonitorSafeMode:
    """Once safe mode is entered, the monitor must exit (not loop on)."""

    def test_monitor_returns_after_triggering(self):
        step = make_step()
        color = MagicMock()
        color.continuous_color_seconds = 5.0
        drum = make_drum_service()

        async def _run():
            # If the monitor didn't return after entering safe mode this
            # would hit wait_for's timeout. Tight bound proves it exits.
            await asyncio.wait_for(
                step._stuck_drum_monitor(color, drum, MagicMock()),
                timeout=0.5,
            )

        run(_run())  # no TimeoutError
        assert drum.collection_failed is True

    def test_enter_safe_mode_sets_collection_failed(self):
        step = make_step()
        drum = make_drum_service()
        step._enter_safe_mode(drum)
        assert drum.collection_failed is True

    def test_enter_safe_mode_clamps_stall_retries_to_one(self):
        step = make_step()
        drum = make_drum_service()
        drum.stall_retries = 3
        step._enter_safe_mode(drum)
        assert drum.stall_retries == 1


class TestStuckMonitorWithFakeColorService:
    """End-to-end: the alternating-drum sequence the FakeColorDetectionService
    produces must NOT trip the watchdog. This is the regression test for the
    bug where _color_first_seen was never cleared between drums."""

    def test_alternating_drums_do_not_trip_safe_mode(self):
        step = make_step()
        svc = FakeColorDetectionService(MagicMock(), sequence=["blue", "pink"] * 4)
        drum = make_drum_service()

        async def _run():
            monitor = asyncio.create_task(
                step._stuck_drum_monitor(svc, drum, MagicMock())
            )
            try:
                # Simulate 8 drum cycles. Each cycle waits + locks + detects,
                # and we hold 0.2s between cycles to mimic sorting work. The
                # *real* fail mode of the previous bug: the first drum's
                # timestamp survived across cycles and tripped at ~1.5s.
                for _ in range(8):
                    svc.reset()
                    await svc.wait_for_color(1.0)
                    svc.lock_color()
                    await svc.detect_color()
                    await asyncio.sleep(0.2)
                # Give the monitor one more tick to react if it were going to.
                await asyncio.sleep(0.15)
                assert drum.collection_failed is False
            finally:
                monitor.cancel()
                try:
                    await monitor
                except asyncio.CancelledError:
                    pass

        run(_run())

    def test_stuck_color_with_real_fake_trips_safe_mode(self):
        # Inverse of the above: if a color truly stays visible (no detect_color
        # ever consumes it), the watchdog MUST fire. Proves the integration
        # path between the two components actually works.
        step = make_step()
        svc = FakeColorDetectionService(MagicMock(), sequence=["blue"])
        drum = make_drum_service()

        async def _run():
            svc.reset()
            await svc.wait_for_color(1.0)
            svc.lock_color()
            # Never call detect_color → continuous_color_seconds grows.
            await asyncio.wait_for(
                step._stuck_drum_monitor(svc, drum, MagicMock()),
                timeout=3.0,
            )

        run(_run())
        assert drum.collection_failed is True
        assert drum.stall_retries == 1
