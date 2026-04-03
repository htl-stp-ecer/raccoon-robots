import asyncio

from libstp import *
from libstp.ui.screen import UIScreen
from libstp.ui.step import UIStep
from libstp.ui.widgets import Center, Column, Row, Spacer, StatusBadge, Text, Widget

from src.hardware.defs import Defs
from src.service.color_detection_service import ColorDetectionService
from src.service.drum_motor_service import DrumMotorService, MotorStalledError
from src.steps.drum_collector.sort_into_slot_step import (
    advance_to_midpoint,
    block_timer_check,
    block_timer_start,
    go_to_empty_slot,
    sort_into_slot,
)
from src.steps.drum_lifting_step import *
from src.steps.servo_steps import close_drum_pusher, open_drum_pusher, use_drum_to_block
from src.steps.wait_for_drum_step import wait_for_drum

# If less than this many seconds remain before the next drum arrives,
# abort and enter safe mode to prevent hardware damage.
TIMING_SAFETY_THRESHOLD = 0.5


class DrumCollectionScreen(UIScreen[None]):
    """Live display of detected color + countdown to next drum."""

    title = "Drum Collection"

    def __init__(self):
        super().__init__()
        self.detected_color: str | None = None
        self.drum_number: int = 0
        self.total_drums: int = 8
        self.countdown: float = 0.0
        self.status: str = "Waiting..."

    def build(self) -> Widget:
        color_text = self.detected_color or "—"
        badge_color = {
            "blue": "blue",
            "pink": "red",
        }.get(self.detected_color or "", "grey")

        return Center(children=[
            Column(children=[
                Text(
                    f"Drum {self.drum_number}/{self.total_drums}",
                    size="title", bold=True, align="center",
                ),
                Spacer(height=12),
                Row(children=[
                    Text("Detected: ", size="large", align="right"),
                    StatusBadge(
                        text=color_text.upper(),
                        color=badge_color,
                        glow=self.detected_color is not None,
                    ),
                ]),
                Spacer(height=12),
                Text(
                    f"Next in: {self.countdown:.1f}s" if self.countdown > 0 else self.status,
                    size="large",
                    align="center",
                    color="#FFD700" if self.countdown > 0 else None,
                ),
            ]),
        ])


START_OFFSET = 9.5
DRUMS = 8
TIME_BETWEEN_DRUMS = 7

@dsl(hidden=True)
class CollectDrumsStep(UIStep):
    """Run drum collection with live UI overlay."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        color_service = robot.get_service(ColorDetectionService)
        screen = DrumCollectionScreen()
        screen.total_drums = DRUMS
        await self.display(screen)

        # Start a background task that refreshes the screen with live data
        ui_task = asyncio.create_task(
            self._ui_updater(screen, color_service, robot),
        )

        try:
            drum_service = robot.get_service(DrumMotorService)

            for i in range(DRUMS):
                drum_number = i + 1
                checkpoint = START_OFFSET + i * TIME_BETWEEN_DRUMS

                # Skip if already in safe mode (motor stalled or timing blown)
                if drum_service.collection_failed:
                    self.warn(f"Skipping drum #{drum_number} — safe mode active")
                    continue

                # Reset detection for new drum + update screen
                color_service.reset()
                screen.drum_number = drum_number
                screen.status = "Waiting for drum..."

                # Phase 1: Receive drum and sort into slot
                # If the motor stalls here, enter safe mode immediately
                try:
                    phase1 = seq([
                        open_drum_pusher(),
                        wait_for_drum(checkpoint=checkpoint),
                        block_timer_start(),
                        drum_align_on_back(),
                        parallel(
                            drum_lifting_down(),
                            sort_into_slot(),
                        ),
                    ])
                    await phase1.run_step(robot)
                except MotorStalledError:
                    self.warn(
                        f"Motor stalled during drum #{drum_number} — "
                        "entering safe mode, keeping servo open"
                    )
                    drum_service.motor.set_velocity(0)
                    Defs.drum_pusher_servo.set_position(170)
                    drum_service.collection_failed = True
                    continue

                # Phase 2: Timing window safety check
                # If the next drum is about to arrive, do NOT close the servo
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

                # Phase 3: Close pusher and move to empty slot (safe to proceed)
                try:
                    phase3 = seq([
                        close_drum_pusher(),
                        wait_for_seconds(0.3),
                        go_to_empty_slot(),
                        block_timer_check(drum_number),
                    ])
                    await phase3.run_step(robot)
                except MotorStalledError:
                    self.warn(
                        f"Motor stalled moving to empty slot after drum "
                        f"#{drum_number} — entering safe mode"
                    )
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
        """Background task: refresh screen with color + countdown."""
        while True:
            # Update detected color (peek, don't consume)
            color = color_service.peek_color
            screen.detected_color = color

            # Update countdown
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

            await asyncio.sleep(0.15)  # ~7 Hz UI updates


@dsl()
def collect_drums() -> CollectDrumsStep:
    return CollectDrumsStep()


class M02CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            collect_drums(),
            advance_to_midpoint(),
        ])
