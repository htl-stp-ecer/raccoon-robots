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
from dataclasses import dataclass

import cv2
import numpy as np
from libstp import GenericRobot, dsl
from libstp.step.calibration import CalibrateStep

from .cam_publisher import CamPublisher
from .screens import (
    BaselineScreen,
    ColorConfirmScreen,
    ColorTestScreen,
)


@dataclass
class ColorCalibration:
    sat_threshold: int = 50


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

    @staticmethod
    def _max_sat(frame: np.ndarray) -> int:
        """Return the maximum HSV saturation value across all pixels in a raw frame."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        return int(hsv[:, :, 1].max())

    async def _capture_frame(self, instruction: str, badge: str) -> np.ndarray | None:
        """Show a capture screen and grab a frame when the user confirms."""
        screen = BaselineScreen(instruction=instruction, badge=badge)
        self._publisher.set_overlay(instruction)
        await self.show(screen)
        return self._publisher.grab_frame()

    def _compute_threshold(
        self, blue_sat: int, pink_sat: int, empty_sat: int,
    ) -> int:
        """Midpoint between the empty max and the lower of the two drum maxes."""
        min_drum = min(blue_sat, pink_sat)
        threshold = (empty_sat + min_drum) // 2
        self.info(
            f"Sat: blue={blue_sat}, pink={pink_sat}, empty={empty_sat} "
            f"-> threshold={threshold} "
            f"(+{threshold - empty_sat} above empty, -{min_drum - threshold} below drums)"
        )
        if threshold <= empty_sat:
            self.warn(
                "Threshold is not above the empty background! "
                "Drum saturation is too close to background - check lighting."
            )
        return threshold

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

            blue_sat = self._max_sat(blue_frame)
            pink_sat = self._max_sat(pink_frame)
            empty_sat = self._max_sat(empty_frame)
            threshold = self._compute_threshold(blue_sat, pink_sat, empty_sat)
            calibration = ColorCalibration(sat_threshold=threshold)

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
                    # "retry" from test screen -> show confirm again
                else:
                    return None  # retry_all -> base class calls _collect again

        except Exception:
            self._stop_publisher()
            raise

    async def _run_test(
        self, robot: GenericRobot, calibration: ColorCalibration,
    ) -> str:
        """Live test: apply threshold and show detections."""
        screen = ColorTestScreen()
        self._publisher.set_overlay("TEST - place a drum")

        async def detect_loop():
            while not screen.is_closed:
                frame = self._publisher.grab_frame()
                if frame is not None:
                    color, confidence, detections = self._detect_from_frame(
                        frame, calibration,
                    )
                    screen.detected_color = color
                    screen.confidence = confidence
                    self._publisher.set_detections(detections)
                    self._publisher.set_overlay(
                        f"Detected: {color.upper()}" if color else "No drum"
                    )
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

    def _detect_from_frame(
        self,
        frame: np.ndarray,
        calibration: ColorCalibration,
    ) -> tuple[str | None, float, list[dict]]:
        """Single-frame detection matching the runtime pipeline."""
        h, w = frame.shape[:2]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

        # Saturation gate on raw frame
        hsv_raw = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        if int(hsv_raw[:, :, 1].max()) < calibration.sat_threshold:
            return None, 0.0, []

        # Pre-process (match USBCamera._preprocess)
        avg = frame.mean(axis=(0, 1))
        avg_all = avg.mean()
        scale = avg_all / (avg + 1e-6)
        pp = np.clip(frame * scale, 0, 255).astype(np.uint8)
        pp = cv2.GaussianBlur(pp, (3, 3), 0)

        hsv = cv2.cvtColor(pp, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(pp, cv2.COLOR_BGR2LAB)

        sat_mask = (hsv[:, :, 1] >= calibration.sat_threshold).astype(np.uint8) * 255
        sat_mask = cv2.morphologyEx(sat_mask, cv2.MORPH_OPEN, kernel)
        sat_mask = cv2.morphologyEx(sat_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(sat_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, 0.0, []

        largest = max(contours, key=cv2.contourArea)
        area = int(cv2.contourArea(largest))
        if area < 300:
            return None, 0.0, []

        x, y, bw, bh = cv2.boundingRect(largest)

        contour_mask = np.zeros(lab.shape[:2], dtype=np.uint8)
        cv2.drawContours(contour_mask, [largest], -1, 255, cv2.FILLED)
        mean_a = float(lab[:, :, 1][contour_mask == 255].mean())
        color = "pink" if mean_a > 128 else "blue"

        confidence = min(area / 2000.0, 1.0)
        detection = {
            "label": color,
            "x": (x + bw / 2) / w,
            "y": (y + bh / 2) / h,
            "width": bw / w,
            "height": bh / h,
            "area": area,
            "confidence": confidence,
        }
        return color, confidence, [detection]

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
        self.info("Color calibration applied to detection service")

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
    return ColorCalibrationStep(
        camera_index=camera_index,
        resolution=resolution,
    )
