import asyncio

from raccoon import GenericRobot, dsl, parallel, seq, wait_for_seconds
from raccoon.ui.step import UIStep

from src.hardware.defs import Defs
from src.service.color_detection_service import ColorDetectionService
from src.service.drum_motor_service import DrumMotorService, MotorStalledError
from src.steps.drum_collector.screens.drum_collection_screen import DrumCollectionScreen
from src.steps.drum_collector.screens.emergency_screen import EmergencyScreen
from src.steps.drum_collector.sort_into_slot_step import (
    advance_to_midpoint,
    block_timer_check,
    block_timer_start,
    go_to_empty_slot,
    sort_into_slot,
)
from src.steps.drum_lifting_step import drum_align_on_back, drum_lifting_down, drum_lifting_up
from src.steps.wait_for_drum_step import wait_for_drum

START_OFFSET = 9.5
DRUMS = 8
TIME_BETWEEN_DRUMS = 7
TIMING_SAFETY_THRESHOLD = 0.5


@dsl(hidden=True)
class CollectDrumsStep(UIStep):
    """Run drum collection with live UI overlay."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        color_service = robot.get_service(ColorDetectionService)
        drum_service = robot.get_service(DrumMotorService)
        screen = DrumCollectionScreen()
        screen.total_drums = DRUMS
        await self.display(screen)

        self._shutdown_triggered = False

        ui_task = asyncio.create_task(
            self._ui_updater(screen, color_service, robot),
        )
        stuck_task = asyncio.create_task(
            self._stuck_drum_monitor(color_service, drum_service, robot),
        )

        # Collection is stricter: one retry, then emergency shutdown.
        # Restored in finally so ejection keeps the default 3-attempt budget.
        prior_stall_retries = drum_service.stall_retries
        drum_service.stall_retries = 2

        try:
            for i in range(DRUMS):
                drum_number = i + 1
                checkpoint = START_OFFSET + i * TIME_BETWEEN_DRUMS

                if drum_service.collection_failed:
                    self.warn(f"Skipping drum #{drum_number} — safe mode active")
                    continue

                screen.drum_number = drum_number
                screen.status = "Waiting for drum..."

                try:
                    elapsed_pre = robot.synchronizer.get_time()
                except (TypeError, AttributeError):
                    elapsed_pre = -1.0
                drum_service.info(
                    f"[DRUM-{drum_number}] START checkpoint={checkpoint:.2f}s "
                    f"elapsed={elapsed_pre:.2f}s "
                    f"pocket={drum_service.current_pocket}"
                )

                try:
                    # Wait for the drum to arrive and get captured
                    phase1a = seq([
                        Defs.drum_pusher_servo.open(),
                        wait_for_drum(checkpoint=checkpoint),
                        block_timer_start(),
                    ])
                    await phase1a.run_step(robot)

                    # Reset detection now so the camera gets a fresh read
                    # of the stationary drum during the settling wait
                    color_service.reset()

                    phase1b = seq([
                        wait_for_seconds(0.5),
                        sort_into_slot(),
                    ])
                    await phase1b.run_step(robot)
                except MotorStalledError:
                    if drum_service.collection_failed:
                        # Already in safe mode (e.g. camera stuck) — skip quietly
                        continue
                    drum_service.motor.brake()
                    if await self._show_emergency_ui(
                        f"Drum Motor is stuck (drum #{drum_number})",
                    ):
                        self._enter_safe_mode(drum_service)
                        continue
                    await self._emergency_shutdown(
                        drum_service,
                        robot,
                        f"Motor stalled during drum #{drum_number} — user did not continue",
                    )
                    return

                if i < DRUMS - 1:
                    next_checkpoint = START_OFFSET + (i + 1) * TIME_BETWEEN_DRUMS
                    try:
                        elapsed = robot.synchronizer.get_time()
                        time_until_next = next_checkpoint - elapsed
                    except (TypeError, AttributeError):
                        time_until_next = float("inf")

                    if time_until_next < TIMING_SAFETY_THRESHOLD:
                        self.warn(
                            f"TIMING BLOWN: only {time_until_next:.2f}s until "
                            f"next drum — entering safe mode to protect hardware"
                        )
                        drum_service.motor.brake()
                        Defs.drum_pusher_servo.device.set_position(Defs.drum_pusher_servo.open.value)
                        drum_service.collection_failed = True
                        continue

                try:
                    elapsed_post = robot.synchronizer.get_time()
                except (TypeError, AttributeError):
                    elapsed_post = -1.0
                drum_service.info(
                    f"[DRUM-{drum_number}] SORTED pocket={drum_service.current_pocket} "
                    f"elapsed={elapsed_post:.2f}s"
                )

                if drum_service.collection_failed:
                    # Safe mode — keep pusher open, skip close/move
                    continue

                try:
                    phase3 = seq([
                        Defs.drum_pusher_servo.close(),
                        wait_for_seconds(0.5),
                        go_to_empty_slot(),
                        block_timer_check(drum_number),
                    ])
                    await phase3.run_step(robot)
                except MotorStalledError:
                    if drum_service.collection_failed:
                        continue
                    drum_service.motor.brake()
                    if await self._show_emergency_ui(
                        f"Drum Motor is stuck (moving to empty slot after drum #{drum_number})",
                    ):
                        self._enter_safe_mode(drum_service)
                        continue
                    await self._emergency_shutdown(
                        drum_service,
                        robot,
                        f"Motor stalled moving to empty slot after drum #{drum_number} — user did not continue",
                    )
                    return

                try:
                    elapsed_done = robot.synchronizer.get_time()
                except (TypeError, AttributeError):
                    elapsed_done = -1.0
                drum_service.info(
                    f"[DRUM-{drum_number}] DONE pocket={drum_service.current_pocket} "
                    f"elapsed={elapsed_done:.2f}s"
                )
                screen.status = "Done"
        finally:
            if drum_service.collection_failed:
                # Safe mode: keep retries at 1 (no retry) for rest of run
                # so eject attempts don't risk hardware damage.
                drum_service.stall_retries = 1
            else:
                drum_service.stall_retries = prior_stall_retries
            for task in (ui_task, stuck_task):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _stuck_drum_monitor(
        self,
        color_service: ColorDetectionService,
        drum_service: DrumMotorService,
        robot: "GenericRobot",
    ) -> None:
        """Watchdog: if a color is continuously visible for >1.5s, the drum is stuck.

        Enters safe mode: stops collecting, keeps pusher open, disables retries,
        but lets the run finish so drums can still be ejected.
        """
        STUCK_THRESHOLD = 1.5  # seconds — normal pass-through is ~400ms
        while True:
            await asyncio.sleep(0.1)
            duration = color_service.continuous_color_seconds
            if duration is not None and duration > STUCK_THRESHOLD:
                self.warn(
                    f"Drum stuck — color visible for {duration:.2f}s "
                    f"(threshold {STUCK_THRESHOLD}s) — entering safe mode"
                )
                self._enter_safe_mode(drum_service)
                return

    def _enter_safe_mode(self, drum_service: DrumMotorService) -> None:
        """Enter safe mode: end collection, keep pusher open, disable retries.

        The run continues so drums can still be ejected.
        """
        drum_service.collection_failed = True
        drum_service.stall_retries = 1  # one attempt, zero retries
        try:
            Defs.drum_pusher_servo.device.set_position(Defs.drum_pusher_servo.open.value)
        except Exception as e:
            self.warn(f"Safe mode pusher-open failed: {e}")
        self.warn("Safe mode active — skipping remaining collection, retries disabled")

    async def _show_emergency_ui(self, reason: str) -> bool:
        """Show emergency screen with 15s countdown. Returns True if user clicks continue."""
        screen = EmergencyScreen()
        screen.reason = reason

        async def _countdown():
            for remaining in range(14, -1, -1):
                await asyncio.sleep(1.0)
                screen.seconds_left = remaining
                try:
                    await screen.refresh()
                except Exception:
                    pass
            screen.close(False)

        countdown_task = asyncio.create_task(_countdown())
        try:
            return await self.show(screen)
        finally:
            countdown_task.cancel()
            try:
                await countdown_task
            except asyncio.CancelledError:
                pass

    async def _emergency_shutdown(
        self,
        drum_service: DrumMotorService,
        robot: "GenericRobot",
        reason: str,
    ) -> None:
        """Dead state: open pusher, lift drum up, then kill the program.

        Called when drum collection enters a state where continuing would
        further harm the hardware. Terminates the process after securing
        the mechanism so no downstream missions run.
        """
        if getattr(self, "_shutdown_triggered", False):
            return
        self._shutdown_triggered = True
        self.warn(f"EMERGENCY SHUTDOWN: {reason}")
        try:
            drum_service.motor.brake()
        except Exception as e:
            self.warn(f"Emergency brake failed: {e}")
        try:
            Defs.drum_pusher_servo.device.set_position(Defs.drum_pusher_servo.open.value)
        except Exception as e:
            self.warn(f"Emergency pusher-open failed: {e}")
        try:
            await drum_lifting_up(always_motor_support=True).run_step(robot)
        except Exception as e:
            self.warn(f"Emergency drum lift failed: {e}")
        self.warn("Killing program — drum collection dead state, no further missions")
        from raccoon.step.watchdog_manager import get_watchdog_manager
        wdt = get_watchdog_manager(robot)
        if wdt._main_task is not None and not wdt._main_task.done():
            wdt._main_task.cancel()
        raise asyncio.CancelledError()

    async def _ui_updater(
        self,
        screen: DrumCollectionScreen,
        color_service: ColorDetectionService,
        robot: "GenericRobot",
    ) -> None:
        while True:
            screen.detected_color = color_service.peek_color
            try:
                elapsed = robot.synchronizer.get_time()
                drum_idx = screen.drum_number - 1
                next_checkpoint = START_OFFSET + drum_idx * TIME_BETWEEN_DRUMS
                remaining = next_checkpoint - elapsed
                screen.countdown = max(0.0, remaining)
                if remaining <= 0:
                    screen.countdown = 0.0
            except (TypeError, AttributeError):
                screen.countdown = 0.0
            try:
                await screen.refresh()
            except Exception:
                pass
            await asyncio.sleep(0.15)


@dsl()
def collect_drums() -> CollectDrumsStep:
    return CollectDrumsStep()
