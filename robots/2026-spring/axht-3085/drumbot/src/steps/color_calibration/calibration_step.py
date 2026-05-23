"""Interactive color calibration backed by the vision daemon.

The setup UI still shows the live ``CamFeed``, but frame capture and OpenCV
analysis now happen in ``src.daemons.vision``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from raccoon import GenericRobot, dsl
from raccoon.step.calibration import CalibrateStep

from src.service.color_detection_service import ColorDetectionService

from .screens import BaselineScreen, ColorConfirmScreen, ColorTestScreen

CONFIDENCE_THRESHOLD = 0.9


@dataclass(frozen=True)
class ColorCalibration:
    sat_threshold: int


def compute_threshold(blue_sat: int, pink_sat: int, empty_sat: int) -> int:
    drum_floor = min(blue_sat, pink_sat)
    return int((empty_sat + drum_floor) / 2)


class ColorCalibrationStep(CalibrateStep[ColorCalibration]):
    def __init__(self):
        super().__init__(store_section="color-detection", store_set="default")

    async def _capture_sample(
        self,
        robot: GenericRobot,
        instruction: str,
        badge: str,
        label: str,
    ) -> int | None:
        service = robot.get_service(ColorDetectionService)
        service.set_overlay(instruction)
        screen = BaselineScreen(instruction=instruction, badge=badge)
        confirmed = await self.show(screen)
        if not confirmed:
            return None
        return service.capture_calibration_sample(label)

    async def _collect(self, robot: GenericRobot) -> ColorCalibration | None:
        blue_sat = await self._capture_sample(robot, "Place BLUE drum in view", "BLUE", "blue")
        pink_sat = await self._capture_sample(robot, "Place PINK drum in view", "PINK", "pink")
        empty_sat = await self._capture_sample(robot, "Remove all drums", "EMPTY", "empty")

        if blue_sat is None or pink_sat is None or empty_sat is None:
            self.warn("Missing samples - retrying calibration")
            await asyncio.sleep(0.3)
            return None

        threshold = compute_threshold(blue_sat, pink_sat, empty_sat)
        self.info(
            f"Sat: blue={blue_sat}, pink={pink_sat}, empty={empty_sat} "
            f"-> threshold={threshold}"
        )
        if threshold <= empty_sat:
            self.warn("Threshold not above empty background - check lighting.")

        calibration = ColorCalibration(sat_threshold=threshold)
        margin_above = threshold - empty_sat
        margin_below = min(blue_sat, pink_sat) - threshold
        if margin_above <= 0 or margin_below <= 0:
            self.warn(
                f"Bad calibration: margin_above={margin_above}, "
                f"margin_below={margin_below} - forcing retry"
            )
            await asyncio.sleep(0.3)
            return None

        while True:
            screen = ColorConfirmScreen(
                sat_threshold=threshold,
                blue_sat=blue_sat,
                pink_sat=pink_sat,
                empty_sat=empty_sat,
            )
            result = await self.show(screen)
            if result == "confirm":
                test_result = await self._run_test(robot, calibration)
                if test_result == "done":
                    return calibration
            else:
                await asyncio.sleep(0.3)
                return None

    async def _run_test(self, robot: GenericRobot, calibration: ColorCalibration) -> str:
        service = robot.get_service(ColorDetectionService)
        service.apply_calibration(calibration.sat_threshold)
        service.set_overlay("TEST - place a drum")
        screen = ColorTestScreen()

        async def refresh_loop():
            while not screen.is_closed:
                color = service.peek_color
                confidence = service.peek_confidence
                screen.detected_color = color
                screen.confidence = confidence
                if color and confidence >= CONFIDENCE_THRESHOLD:
                    service.set_overlay(f"DRUM: {color.upper()} ({confidence:.0%})")
                elif color:
                    service.set_overlay(f"weak: {color} ({confidence:.0%})")
                else:
                    service.set_overlay("No drum")
                await screen.refresh()
                await asyncio.sleep(0.1)

        task = asyncio.create_task(refresh_loop())
        result = await self.show(screen)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return result or "done"

    async def _confirm(
        self, robot: GenericRobot, calibration: ColorCalibration,
    ) -> tuple[bool, ColorCalibration]:
        await self.close_ui()
        return True, calibration

    def _apply(self, robot: GenericRobot, calibration: ColorCalibration) -> None:
        service = robot.get_service(ColorDetectionService)
        service.apply_calibration(sat_threshold=calibration.sat_threshold)
        self.info(f"Color calibration applied: sat_threshold={calibration.sat_threshold}")

    def _serialize(self, calibration: ColorCalibration) -> dict:
        return {"sat_threshold": calibration.sat_threshold}

    def _deserialize(self, data: dict) -> ColorCalibration:
        return ColorCalibration(sat_threshold=int(data.get("sat_threshold", 50)))


@dsl()
def calibrate_colors() -> ColorCalibrationStep:
    """Interactive saturation-gate calibration for daemon-backed drum detection."""
    return ColorCalibrationStep()
