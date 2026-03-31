"""Interactive camera color calibration step.

Walks the user through:
1. Tap on blue drum → sample HSV from tap region
2. Tap on pink drum → sample HSV from tap region
3. Clear view → sample background HSV
4. Compute tight HSV ranges that match the drums but NOT the background
5. Live test phase to verify

Saves to racoon.calibration.yml and applies to ColorDetectionService.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import cv2
import numpy as np
from libstp import GenericRobot, dsl
from libstp.step.calibration import CalibrateStep

from .cam_publisher import CamPublisher
from .screens import (
    BaselineScreen,
    ColorConfirmScreen,
    ColorTestScreen,
    SamplingScreen,
)

# Padding on the percentile range before baseline exclusion.
H_MARGIN = 15
S_MARGIN = 25
V_MARGIN = 30

# Tap ROI radius as fraction of frame shortest side.
TAP_ROI_FRACTION = 0.12

# Minimum frames to consider a valid sample.
MIN_SAMPLE_FRAMES = 5

# Absolute floor for min_area (pixels).
MIN_AREA_FLOOR = 300

# Maximum allowed false-positive rate on background pixels.
MAX_BG_MATCH_RATE = 0.10


@dataclass
class ColorCalibration:
    blue_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]] = field(default_factory=list)
    pink_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]] = field(default_factory=list)
    min_area: int = MIN_AREA_FLOOR


class ColorCalibrationStep(CalibrateStep[ColorCalibration]):
    def __init__(
        self,
        camera_index: int | str = "/dev/video0",
        resolution: tuple[int, int] = (320, 240),
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

    # -- HSV sampling --------------------------------------------------------

    def _sample_roi_at(
        self, frame: np.ndarray, norm_x: float, norm_y: float,
    ) -> np.ndarray | None:
        """Extract HSV pixels from a circular region around (norm_x, norm_y)."""
        h, w = frame.shape[:2]
        cx = int(norm_x * w)
        cy = int(norm_y * h)
        radius = int(min(w, h) * TAP_ROI_FRACTION)

        # Clamp to frame bounds
        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)
        if x2 <= x1 or y2 <= y1:
            return None

        roi = frame[y1:y2, x1:x2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        return hsv.reshape(-1, 3)

    def _sample_full_frame(self, frame: np.ndarray) -> np.ndarray:
        """Extract HSV pixels from the entire frame (for baseline)."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        return hsv.reshape(-1, 3)

    # -- Range computation with iterative baseline exclusion -----------------

    def _compute_range(
        self,
        color_pixels: np.ndarray,
        baseline_pixels: np.ndarray | None = None,
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        """Compute an HSV range that matches the drum but not the background.

        1. Start with tight percentile range of the color sample + small margin.
        2. If baseline provided, iteratively raise saturation floor until
           the false-positive rate on background drops below threshold.
           If that's not enough, tighten hue and value too.
        """
        ch = color_pixels[:, 0].astype(float)
        cs = color_pixels[:, 1].astype(float)
        cv_ = color_pixels[:, 2].astype(float)

        # Tight range from color sample
        h_lo = max(0, int(np.percentile(ch, 10) - H_MARGIN))
        h_hi = min(179, int(np.percentile(ch, 90) + H_MARGIN))
        s_lo = max(0, int(np.percentile(cs, 10) - S_MARGIN))
        s_hi = min(255, int(np.percentile(cs, 90) + S_MARGIN))
        v_lo = max(0, int(np.percentile(cv_, 10) - V_MARGIN))
        v_hi = min(255, int(np.percentile(cv_, 90) + V_MARGIN))

        if baseline_pixels is None or len(baseline_pixels) == 0:
            return (h_lo, s_lo, v_lo), (h_hi, s_hi, v_hi)

        bh = baseline_pixels[:, 0].astype(float)
        bs = baseline_pixels[:, 1].astype(float)
        bv = baseline_pixels[:, 2].astype(float)
        n_bg = len(baseline_pixels)

        def bg_match_rate():
            return float(np.sum(
                (bh >= h_lo) & (bh <= h_hi) &
                (bs >= s_lo) & (bs <= s_hi) &
                (bv >= v_lo) & (bv <= v_hi)
            )) / n_bg

        rate = bg_match_rate()
        self.info(
            f"  Initial range H:{h_lo}-{h_hi} S:{s_lo}-{s_hi} V:{v_lo}-{v_hi}, "
            f"BG match: {rate:.1%}"
        )

        # Strategy 1: raise saturation floor (most effective for colored objects)
        color_s_floor = int(np.percentile(cs, 2))
        while rate > MAX_BG_MATCH_RATE and s_lo < color_s_floor:
            s_lo = min(s_lo + 5, color_s_floor)
            rate = bg_match_rate()

        if rate <= MAX_BG_MATCH_RATE:
            self.info(f"  After S tightening: S_lo={s_lo}, BG match: {rate:.1%}")
            return (h_lo, s_lo, v_lo), (h_hi, s_hi, v_hi)

        # Strategy 2: tighten value bounds
        color_v_lo_floor = int(np.percentile(cv_, 2))
        color_v_hi_ceil = int(np.percentile(cv_, 98))
        while rate > MAX_BG_MATCH_RATE and v_lo < color_v_lo_floor:
            v_lo = min(v_lo + 5, color_v_lo_floor)
            rate = bg_match_rate()
        while rate > MAX_BG_MATCH_RATE and v_hi > color_v_hi_ceil:
            v_hi = max(v_hi - 5, color_v_hi_ceil)
            rate = bg_match_rate()

        if rate <= MAX_BG_MATCH_RATE:
            self.info(
                f"  After V tightening: V:{v_lo}-{v_hi}, BG match: {rate:.1%}"
            )
            return (h_lo, s_lo, v_lo), (h_hi, s_hi, v_hi)

        # Strategy 3: tighten hue bounds
        color_h_lo_floor = int(np.percentile(ch, 2))
        color_h_hi_ceil = int(np.percentile(ch, 98))
        while rate > MAX_BG_MATCH_RATE and (h_lo < color_h_lo_floor or h_hi > color_h_hi_ceil):
            if h_lo < color_h_lo_floor:
                h_lo = min(h_lo + 2, color_h_lo_floor)
            if h_hi > color_h_hi_ceil:
                h_hi = max(h_hi - 2, color_h_hi_ceil)
            rate = bg_match_rate()

        self.info(
            f"  Final range H:{h_lo}-{h_hi} S:{s_lo}-{s_hi} V:{v_lo}-{v_hi}, "
            f"BG match: {rate:.1%}"
        )
        if rate > MAX_BG_MATCH_RATE:
            self.warn(
                f"  Could not reduce BG match below {MAX_BG_MATCH_RATE:.0%} "
                f"(stuck at {rate:.1%}). Consider better lighting."
            )

        return (h_lo, s_lo, v_lo), (h_hi, s_hi, v_hi)

    def _compute_pink_ranges(
        self,
        all_pixels: np.ndarray,
        baseline_pixels: np.ndarray | None = None,
    ) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
        """Compute pink HSV ranges, handling hue wraparound near 0/180."""
        h_vals = all_pixels[:, 0].astype(float)

        low_count = np.sum(h_vals < 30)
        high_count = np.sum(h_vals > 150)

        if low_count > len(h_vals) * 0.1 and high_count > len(h_vals) * 0.1:
            high_pixels = all_pixels[all_pixels[:, 0] > 90]
            low_pixels = all_pixels[all_pixels[:, 0] <= 90]
            ranges = []
            if len(high_pixels) > 0:
                ranges.append(self._compute_range(high_pixels, baseline_pixels))
            if len(low_pixels) > 0:
                ranges.append(self._compute_range(low_pixels, baseline_pixels))
            return ranges if ranges else [self._compute_range(all_pixels, baseline_pixels)]

        return [self._compute_range(all_pixels, baseline_pixels)]

    # -- Noise area measurement (secondary safety net) -----------------------

    def _measure_noise_area(
        self,
        frame: np.ndarray,
        hsv_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]],
    ) -> int:
        """Return the largest blob area for the given HSV ranges in one frame."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        kernel = np.ones((3, 3), np.uint8)

        mask = None
        for lower, upper in hsv_ranges:
            m = cv2.inRange(hsv, np.array(lower), np.array(upper))
            mask = m if mask is None else cv2.bitwise_or(mask, m)
        if mask is None:
            return 0

        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0
        return int(max(cv2.contourArea(c) for c in contours))

    # -- Interactive sampling ------------------------------------------------

    async def _sample_color(
        self, color_name: str, instruction: str,
    ) -> list[np.ndarray] | None:
        """Show sampling screen with tap-to-select. Returns raw pixel arrays."""
        screen = SamplingScreen(color_name, instruction)
        self._publisher.set_overlay(f"Sampling: {color_name.upper()}")
        self._publisher.set_roi_enabled(False)

        all_pixels: list[np.ndarray] = []

        async def collect_samples():
            screen.sampling = True
            await screen.refresh()
            while not screen.is_closed:
                if screen.tap_x is not None and screen.tap_y is not None:
                    frame = self._publisher.grab_frame()
                    if frame is not None:
                        pixels = self._sample_roi_at(
                            frame, screen.tap_x, screen.tap_y,
                        )
                        if pixels is not None:
                            all_pixels.append(pixels)
                            combined = np.vstack(all_pixels)
                            screen.h_mean = float(np.mean(combined[:, 0]))
                            screen.s_mean = float(np.mean(combined[:, 1]))
                            screen.v_mean = float(np.mean(combined[:, 2]))
                            screen.sample_count = len(all_pixels)
                            await screen.refresh()
                await asyncio.sleep(0.15)

        task = asyncio.create_task(collect_samples())
        confirmed = await self.show(screen)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        if not confirmed or len(all_pixels) < MIN_SAMPLE_FRAMES:
            return None

        return all_pixels

    async def _sample_baseline(self) -> list[np.ndarray]:
        """Sample the empty background (full frame). Returns raw pixel arrays."""
        screen = BaselineScreen()
        self._publisher.set_overlay("BASELINE - remove drums")
        self._publisher.set_roi_enabled(False)

        all_pixels: list[np.ndarray] = []

        async def collect_baseline():
            screen.sampling = True
            await screen.refresh()
            while not screen.is_closed:
                frame = self._publisher.grab_frame()
                if frame is not None:
                    pixels = self._sample_full_frame(frame)
                    all_pixels.append(pixels)
                    screen.sample_count = len(all_pixels)
                    await screen.refresh()
                await asyncio.sleep(0.15)

        task = asyncio.create_task(collect_baseline())
        await self.show(screen)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        return all_pixels

    # -- CalibrateStep hooks -------------------------------------------------

    async def _collect(self, robot: GenericRobot) -> ColorCalibration | None:
        self._start_publisher()
        try:
            self._publisher.set_overlay("Color Calibration")

            # Phase 1 & 2: tap on drums to sample colors
            blue_pixels = await self._sample_color(
                "blue", "Place BLUE drum, tap on it",
            )
            pink_pixels = await self._sample_color(
                "pink", "Place PINK drum, tap on it",
            )

            if blue_pixels is None and pink_pixels is None:
                return None

            # Phase 3: sample empty background
            baseline_pixel_list = await self._sample_baseline()
            baseline = (
                np.vstack(baseline_pixel_list)
                if baseline_pixel_list
                else None
            )
            if baseline is not None:
                # Subsample to keep memory reasonable
                if len(baseline) > 500_000:
                    idx = np.random.choice(len(baseline), 500_000, replace=False)
                    baseline = baseline[idx]

            # Compute ranges, tightened against baseline
            self.info("Computing blue ranges...")
            blue_ranges = []
            if blue_pixels:
                combined = np.vstack(blue_pixels)
                blue_ranges = [self._compute_range(combined, baseline)]

            self.info("Computing pink ranges...")
            pink_ranges = []
            if pink_pixels:
                combined = np.vstack(pink_pixels)
                pink_ranges = self._compute_pink_ranges(combined, baseline)

            # Measure remaining noise as secondary safety net
            min_area = MIN_AREA_FLOOR
            all_ranges = blue_ranges + pink_ranges
            if all_ranges:
                worst_noise = 0
                for _ in range(10):
                    frame = self._publisher.grab_frame()
                    if frame is not None:
                        for r in [blue_ranges, pink_ranges]:
                            if r:
                                area = self._measure_noise_area(frame, r)
                                worst_noise = max(worst_noise, area)
                    await asyncio.sleep(0.05)
                min_area = max(int(worst_noise * 2) + 100, MIN_AREA_FLOOR)
                self.info(f"Noise check: worst={worst_noise}px, min_area={min_area}px")

            return ColorCalibration(
                blue_ranges=blue_ranges,
                pink_ranges=pink_ranges,
                min_area=min_area,
            )
        except Exception:
            self._stop_publisher()
            raise

    async def _confirm(
        self, robot: GenericRobot, calibration: ColorCalibration,
    ) -> tuple[bool, ColorCalibration]:
        blue_display = calibration.blue_ranges[0] if calibration.blue_ranges else None
        pink_display = calibration.pink_ranges or None

        screen = ColorConfirmScreen(
            blue_range=blue_display,
            pink_ranges=pink_display,
            min_area=calibration.min_area,
        )
        confirmed = await self.show(screen)

        if confirmed:
            await self._run_test(robot, calibration)

        # Stop publisher before returning — its Transport's background
        # LCM subscriptions must be cleaned up before the next UIStep
        # tries to use the same channels.
        self._stop_publisher()
        await self.close_ui()

        return confirmed, calibration

    async def _run_test(
        self, robot: GenericRobot, calibration: ColorCalibration,
    ) -> None:
        """Live test phase: detect colors and show results."""
        screen = ColorTestScreen()
        self._publisher.set_overlay("TEST MODE - place drum")

        colors_config = {}
        if calibration.blue_ranges:
            colors_config["blue"] = calibration.blue_ranges
        if calibration.pink_ranges:
            colors_config["pink"] = calibration.pink_ranges
        min_area = calibration.min_area

        async def detect_loop():
            while not screen.is_closed:
                frame = self._publisher.grab_frame()
                if frame is not None:
                    color, confidence, detections = self._detect_from_frame(
                        frame, colors_config, min_area,
                    )
                    screen.detected_color = color
                    screen.confidence = confidence
                    self._publisher.set_detections(detections)
                    overlay = f"Detected: {color.upper()}" if color else "No detection"
                    self._publisher.set_overlay(overlay)
                    await screen.refresh()
                await asyncio.sleep(0.1)

        task = asyncio.create_task(detect_loop())
        await self.show(screen)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def _detect_from_frame(
        self,
        frame: np.ndarray,
        colors: dict[str, list[tuple[tuple[int, ...], tuple[int, ...]]]],
        min_area: int = MIN_AREA_FLOOR,
    ) -> tuple[str | None, float, list[dict]]:
        """Run single-frame color detection with calibrated thresholds."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, w = frame.shape[:2]
        kernel = np.ones((3, 3), np.uint8)
        best_color = None
        best_area = 0
        detections = []

        for name, ranges in colors.items():
            mask = None
            for lower, upper in ranges:
                m = cv2.inRange(hsv, np.array(lower), np.array(upper))
                mask = m if mask is None else cv2.bitwise_or(mask, m)
            if mask is None:
                continue
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            largest = max(contours, key=cv2.contourArea)
            area = int(cv2.contourArea(largest))
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(largest)
            cx = (x + bw / 2) / w
            cy = (y + bh / 2) / h
            detections.append({
                "label": name,
                "x": cx,
                "y": cy,
                "width": bw / w,
                "height": bh / h,
                "area": area,
                "confidence": min(area / 5000.0, 1.0),
            })
            if area > best_area:
                best_area = area
                best_color = name

        confidence = min(best_area / 5000.0, 1.0) if best_color else 0.0
        return best_color, confidence, detections

    def _apply(self, robot: GenericRobot, calibration: ColorCalibration) -> None:
        from src.service.color_detection_service import ColorDetectionService

        service = robot.get_service(ColorDetectionService)
        service.apply_calibration(
            calibration.blue_ranges,
            calibration.pink_ranges,
            calibration.min_area,
        )
        self.info("Color calibration applied to detection service")

    def _serialize(self, calibration: ColorCalibration) -> dict:
        return {
            "blue_ranges": [
                [list(lo), list(hi)] for lo, hi in calibration.blue_ranges
            ],
            "pink_ranges": [
                [list(lo), list(hi)] for lo, hi in calibration.pink_ranges
            ],
            "min_area": calibration.min_area,
        }

    def _deserialize(self, data: dict) -> ColorCalibration:
        return ColorCalibration(
            blue_ranges=[
                (tuple(lo), tuple(hi)) for lo, hi in data.get("blue_ranges", [])
            ],
            pink_ranges=[
                (tuple(lo), tuple(hi)) for lo, hi in data.get("pink_ranges", [])
            ],
            min_area=data.get("min_area", MIN_AREA_FLOOR),
        )


@dsl()
def calibrate_colors(
    camera_index: int | str = "/dev/video0",
    resolution: tuple[int, int] = (320, 240),
) -> ColorCalibrationStep:
    """Interactive HSV color calibration for drum detection."""
    return ColorCalibrationStep(
        camera_index=camera_index,
        resolution=resolution,
    )
