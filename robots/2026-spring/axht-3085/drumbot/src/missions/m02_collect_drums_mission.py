import asyncio

from libstp import *
from libstp.ui.screen import UIScreen
from libstp.ui.step import UIStep
from libstp.ui.widgets import Center, Column, Row, Spacer, StatusBadge, Text, Widget

from src.service.color_detection_service import ColorDetectionService
from src.steps.drum_collector.sort_into_slot_step import (
    advance_to_midpoint,
    block_timer_check,
    block_timer_start,
    go_to_empty_slot,
    sort_into_slot,
)
from src.steps.drum_lifting_step import *
from src.steps.servo_steps import close_drum_pusher, open_drum_pusher, use_drum_to_block


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


START_OFFSET = 10
DRUMS = 8
TIME_BETWEEN_DRUMS = 7
TIME_BEFORE_COLLECTING = 0.3


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
            for i in range(DRUMS):
                drum_number = i + 1
                checkpoint = START_OFFSET + i * TIME_BETWEEN_DRUMS

                # Reset detection for new drum + update screen
                color_service.reset()
                screen.drum_number = drum_number
                screen.status = "Waiting for drum..."

                # Build and run the block steps
                block = seq([
                    open_drum_pusher(),
                    wait_for_checkpoint(checkpoint + TIME_BEFORE_COLLECTING),
                    block_timer_start(),
                    use_drum_to_block(),
                    drum_align_on_back(),
                    parallel(
                        drum_lifting_down(),
                        sort_into_slot(),
                    ),
                    close_drum_pusher(),
                    go_to_empty_slot(),
                    block_timer_check(drum_number),
                ])
                await block.run_step(robot)

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
            drum_lifting_down(slow_mode=False),
            collect_drums(),
            advance_to_midpoint(),
        ])
