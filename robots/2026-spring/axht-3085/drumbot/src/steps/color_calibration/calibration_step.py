"""Interactive camera color calibration step.

Calibrates a single saturation gate threshold by capturing three frames:
  1. Blue drum in view  - record max HSV saturation
  2. Pink drum in view  - record max HSV saturation
  3. Empty (no drum)    - record max HSV saturation

Threshold = midpoint between the empty max and the minimum drum max.
Blue vs pink is decided at runtime via the LAB a* channel - no calibration needed.

Saves to racoon.calibration.yml and applies to ColorDetectionService.
"""

from __future__ import annotations

import asyncio

import numpy as np
from libstp import GenericRobot, dsl
from libstp.step.calibration import CalibrateStep

from .cam_publisher import CamPublisher
from .color_frame_analysis import (
    ColorCalibration,
    compute_threshold,
    detect_color_from_frame,
    dominant_blob,
    save_debug_frame,
    save_debug_mask,
)
from .screens import BaselineScreen, ColorConfirmScreen, ColorTestScreen

CONFIDENCE_THRESHOLD = 0.7  # must match PRESENCE_THRESHOLD in ColorDetectionService


class ColorCalibrationStep(CalibrateStep[ColorCalibration]):
    def __init__(
        self,
        camera_index: int | str = "/dev/video0",
        resolution: tuple[int, int] = (160, 120),
    ):
        super().__init__(store_section="color-detection", store_set="default")
        self._camera_index = camera_index
        self._resolution = resolution
        self._publisher: CamPublisher | None = None

    def _start_publisher(self) -> None:
        self._stop_publisher()
        self._publisher = CamPublisher(
            camera_index=self._camera_index,
            resolution=self._resolution,
        )
        self._publisher.start()

    def _stop_publisher(self) -> None:
        if self._publisher:
            self._publisher.stop()
            self._publisher = None

    async def _capture_frame(self, instruction: str, badge: str) -> np.ndarray | None:
        screen = BaselineScreen(instruction=instruction, badge=badge)
        self._publisher.set_overlay(instruction)
        await self.show(screen)
        return self._publisher.grab_frame()

    # -- CalibrateStep hooks -------------------------------------------------

    async def _collect(self, robot: GenericRobot) -> ColorCalibration | None:
        self._start_publisher()
        try:
            blue_frame = await self._capture_frame("Place BLUE drum in view", "BLUE")
            pink_frame = await self._capture_frame("Place PINK drum in view", "PINK")
            empty_frame = await self._capture_frame("Remove all drums", "EMPTY")

            if blue_frame is None or pink_frame is None or empty_frame is None:
                self.warn("Missing frames - retrying calibration")
                return None

            blue_sat, _ = dominant_blob(blue_frame)
            pink_sat, _ = dominant_blob(pink_frame)
            empty_sat, _ = dominant_blob(empty_frame)
            threshold = compute_threshold(blue_sat, pink_sat, empty_sat)
            self.info(
                f"Sat: blue={blue_sat}, pink={pink_sat}, empty={empty_sat} "
                f"-> threshold={threshold}"
            )
            if threshold <= empty_sat:
                self.warn("Threshold not above empty background — check lighting.")

            calibration = ColorCalibration(sat_threshold=threshold)
            save_debug_mask({"blue": blue_frame, "pink": pink_frame, "empty": empty_frame}, threshold)
            save_debug_frame(empty_frame)

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
                    return None  # retry_all

        except Exception:
            self._stop_publisher()
            raise

    async def _run_test(self, robot: GenericRobot, calibration: ColorCalibration) -> str:
        screen = ColorTestScreen()
        self._publisher.set_overlay("TEST - place a drum")

        async def detect_loop():
            while not screen.is_closed:
                frame = self._publisher.grab_frame()
                if frame is not None:
                    color, confidence, detections = detect_color_from_frame(frame, calibration)
                    screen.detected_color = color
                    screen.confidence = confidence
                    self._publisher.set_detections(detections)
                    if color and confidence >= CONFIDENCE_THRESHOLD:
                        overlay = f"DRUM: {color.upper()} ({confidence:.0%})"
                    elif color:
                        overlay = f"weak: {color} ({confidence:.0%})"
                    else:
                        overlay = "No drum"
                    self._publisher.set_overlay(overlay)
                    await screen.refresh()
                await asyncio.sleep(0.1)

        task = asyncio.create_task(detect_loop())
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
        self._stop_publisher()
        await self.close_ui()
        return True, calibration

    def _apply(self, robot: GenericRobot, calibration: ColorCalibration) -> None:
        from src.service.color_detection_service import ColorDetectionService
        service = robot.get_service(ColorDetectionService)
        service.apply_calibration(sat_threshold=calibration.sat_threshold)
        self.info(f"Color calibration applied: sat_threshold={calibration.sat_threshold}")

    def _serialize(self, calibration: ColorCalibration) -> dict:
        return {"sat_threshold": calibration.sat_threshold}

    def _deserialize(self, data: dict) -> ColorCalibration:
        return ColorCalibration(sat_threshold=int(data.get("sat_threshold", 50)))


@dsl()
def calibrate_colors(
    camera_index: int | str = "/dev/video0",
    resolution: tuple[int, int] = (160, 120),
) -> ColorCalibrationStep:
    """Interactive saturation-gate calibration for drum detection."""
    return ColorCalibrationStep(camera_index=camera_index, resolution=resolution)
