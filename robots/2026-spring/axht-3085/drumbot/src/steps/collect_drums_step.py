import asyncio

from raccoon import GenericRobot, dsl, parallel, seq, wait_for_seconds
from raccoon.ui.step import UIStep

from src.hardware.defs import Defs
from src.service.color_detection_service import ColorDetectionService
from src.service.drum_motor_service import DrumMotorService, MotorStalledError
from src.steps.drum_collector.screens.drum_collection_screen import DrumCollectionScreen
from src.steps.drum_collector.sort_into_slot_step import (
    advance_to_midpoint,
    block_timer_check,
    block_timer_start,
    go_to_empty_slot,
    sort_into_slot,
)
from src.steps.drum_lifting_step import drum_align_on_back, drum_lifting_down
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

        ui_task = asyncio.create_task(
            self._ui_updater(screen, color_service, robot),
        )
        stuck_task = asyncio.create_task(
            self._stuck_drum_monitor(color_service, drum_service),
        )

        try:
            for i in range(DRUMS):
                drum_number = i + 1
                checkpoint = START_OFFSET + i * TIME_BETWEEN_DRUMS

                if drum_service.collection_failed:
                    self.warn(f"Skipping drum #{drum_number} — safe mode active")
                    continue

                color_service.reset()
                screen.drum_number = drum_number
                screen.status = "Waiting for drum..."

                try:
                    phase1 = seq([
                        Defs.drum_pusher_servo.open(),
                        wait_for_drum(checkpoint=checkpoint),
                        block_timer_start(),
                        wait_for_seconds(0.5),
                        #drum_align_on_back(),
                        #parallel(
                        #    drum_lifting_down(),
                            sort_into_slot(),
                        #),
                    ])
                    await phase1.run_step(robot)
                except MotorStalledError:
                    self.warn(f"Motor stalled during drum #{drum_number} — entering safe mode")
                    drum_service.motor.brake()
                    Defs.drum_pusher_servo.device.set_position(Defs.drum_pusher_servo.open.value)
                    drum_service.collection_failed = True
                    continue

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
                    phase3 = seq([
                        Defs.drum_pusher_servo.close(),
                        wait_for_seconds(0.5),
                        go_to_empty_slot(),
                        block_timer_check(drum_number),
                    ])
                    await phase3.run_step(robot)
                except MotorStalledError:
                    self.warn(f"Motor stalled moving to empty slot after drum #{drum_number} — entering safe mode")
                    drum_service.motor.brake()
                    Defs.drum_pusher_servo.device.set_position(Defs.drum_pusher_servo.open.value)
                    drum_service.collection_failed = True
                    continue

                screen.status = "Done"
        finally:
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
    ) -> None:
        """Watchdog: if a color is continuously visible for >1s, the drum is stuck.

        Immediately opens the pusher servo and kills the drum motor to prevent
        hardware damage, then sets collection_failed so the main loop aborts.
        """
        STUCK_THRESHOLD = 1.0  # seconds — normal pass-through is ~400ms
        while True:
            await asyncio.sleep(0.1)
            duration = color_service.continuous_color_seconds
            if duration is not None and duration > STUCK_THRESHOLD:
                self.warn(
                    f"Drum stuck detected — color visible for {duration:.2f}s "
                    f"(threshold {STUCK_THRESHOLD}s) — opening servo and stopping motor"
                )
                drum_service.motor.brake()
                Defs.drum_pusher_servo.device.set_position(Defs.drum_pusher_servo.open.value)  # open
                drum_service.collection_failed = True
                return  # watchdog done; main loop will see collection_failed

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
