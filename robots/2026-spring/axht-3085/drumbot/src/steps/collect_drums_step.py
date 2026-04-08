import asyncio

from libstp import GenericRobot, dsl, parallel, seq, wait_for_seconds
from libstp.ui.step import UIStep

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
from src.steps.servo_steps import close_drum_pusher, open_drum_pusher
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
                        open_drum_pusher(),
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
                    drum_service.motor.set_velocity(0)
                    Defs.drum_pusher_servo.set_position(170)
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
                        drum_service.motor.set_velocity(0)
                        Defs.drum_pusher_servo.set_position(170)
                        drum_service.collection_failed = True
                        continue

                try:
                    phase3 = seq([
                        close_drum_pusher(),
                        wait_for_seconds(0.5),
                        go_to_empty_slot(),
                        block_timer_check(drum_number),
                    ])
                    await phase3.run_step(robot)
                except MotorStalledError:
                    self.warn(f"Motor stalled moving to empty slot after drum #{drum_number} — entering safe mode")
                    drum_service.motor.set_velocity(0)
                    Defs.drum_pusher_servo.set_position(170)
                    drum_service.collection_failed = True
                    continue

                screen.status = "Done"
        finally:
            ui_task.cancel()
            try:
                await ui_task
            except asyncio.CancelledError:
                pass

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
