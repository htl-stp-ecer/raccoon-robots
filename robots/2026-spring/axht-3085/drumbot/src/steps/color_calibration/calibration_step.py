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
    # Both colors use LAB color space + HSV saturation gate
    blue_lab_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]] = field(default_factory=list)
    blue_sat_min: int = 0
    pink_lab_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]] = field(default_factory=list)
    pink_sat_min: int = 0
    min_area: int = MIN_AREA_FLOOR


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

    # -- Preprocessing (matches USBCamera._preprocess) -----------------------

    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        """Gray-world white balance + Gaussian blur."""
        avg = frame.mean(axis=(0, 1))
        avg_all = avg.mean()
        scale = avg_all / (avg + 1e-6)
        wb = np.clip(frame * scale, 0, 255).astype(np.uint8)
        return cv2.GaussianBlur(wb, (3, 3), 0)

    # -- Pixel sampling --------------------------------------------------------

    def _extract_roi(
        self, frame: np.ndarray, norm_x: float, norm_y: float,
    ) -> np.ndarray | None:
        """Extract BGR ROI pixels from a circular region."""
        h, w = frame.shape[:2]
        cx = int(norm_x * w)
        cy = int(norm_y * h)
        radius = int(min(w, h) * TAP_ROI_FRACTION)

        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)
        if x2 <= x1 or y2 <= y1:
            return None

        return frame[y1:y2, x1:x2]

    def _sample_roi_at(
        self, frame: np.ndarray, norm_x: float, norm_y: float,
    ) -> np.ndarray | None:
        """Extract HSV pixels from a circular region around (norm_x, norm_y)."""
        roi = self._extract_roi(frame, norm_x, norm_y)
        if roi is None:
            return None
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        return hsv.reshape(-1, 3)

    def _sample_roi_lab_at(
        self, frame: np.ndarray, norm_x: float, norm_y: float,
    ) -> np.ndarray | None:
        """Extract LAB pixels from a circular region around (norm_x, norm_y)."""
        roi = self._extract_roi(frame, norm_x, norm_y)
        if roi is None:
            return None
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        return lab.reshape(-1, 3)

    def _sample_full_frame(self, frame: np.ndarray) -> np.ndarray:
        """Extract HSV pixels from the entire frame (for baseline)."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        return hsv.reshape(-1, 3)

    def _sample_full_frame_lab(self, frame: np.ndarray) -> np.ndarray:
        """Extract LAB pixels from the entire frame (for baseline)."""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        return lab.reshape(-1, 3)

    # -- Range computation with iterative baseline exclusion -----------------

    def _compute_range(
        self,
        color_pixels: np.ndarray,
        baseline_pixels: np.ndarray | None = None,
        h_margin: int = H_MARGIN,
        s_margin: int = S_MARGIN,
        v_margin: int = V_MARGIN,
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        """Compute a 3-channel range that matches the color but not the background.

        Works for both HSV and LAB pixel arrays — channels are treated generically.

        1. Start with tight percentile range of the color sample + margin.
        2. If baseline provided, iteratively tighten until the false-positive
           rate on background drops below threshold.
        """
        ch = color_pixels[:, 0].astype(float)
        cs = color_pixels[:, 1].astype(float)
        cv_ = color_pixels[:, 2].astype(float)

        # Tight range from color sample
        h_lo = max(0, int(np.percentile(ch, 10) - h_margin))
        h_hi = min(255, int(np.percentile(ch, 90) + h_margin))
        s_lo = max(0, int(np.percentile(cs, 10) - s_margin))
        s_hi = min(255, int(np.percentile(cs, 90) + s_margin))
        v_lo = max(0, int(np.percentile(cv_, 10) - v_margin))
        v_hi = min(255, int(np.percentile(cv_, 90) + v_margin))

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

    # -- Noise area measurement (secondary safety net) -----------------------

    def _measure_noise_area(
        self,
        frame: np.ndarray,
        ranges: list[tuple[tuple[int, ...], tuple[int, ...]]],
        color_space: str = "hsv",
        sat_min: int = 0,
    ) -> int:
        """Return the largest blob area for the given ranges in one frame."""
        pp = self._preprocess(frame)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

        if color_space == "lab":
            converted = cv2.cvtColor(pp, cv2.COLOR_BGR2LAB)
        else:
            converted = cv2.cvtColor(pp, cv2.COLOR_BGR2HSV)

        mask = None
        for lower, upper in ranges:
            m = cv2.inRange(converted, np.array(lower), np.array(upper))
            mask = m if mask is None else cv2.bitwise_or(mask, m)
        if mask is None:
            return 0

        # Apply saturation gate for LAB mode
        if color_space == "lab" and sat_min > 0:
            hsv = cv2.cvtColor(pp, cv2.COLOR_BGR2HSV)
            sat_mask = (hsv[:, :, 1] >= sat_min).astype(np.uint8) * 255
            mask = cv2.bitwise_and(mask, sat_mask)

        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0
        return int(max(cv2.contourArea(c) for c in contours))

    # -- Interactive sampling ------------------------------------------------

    @dataclass
    class _ColorSamples:
        hsv: list[np.ndarray]
        lab: list[np.ndarray]

    async def _sample_color(
        self, color_name: str, instruction: str,
    ) -> _ColorSamples | None:
        """Show sampling screen with tap-to-select. Returns HSV + LAB pixel arrays."""
        screen = SamplingScreen(color_name, instruction)
        self._publisher.set_overlay(f"Sampling: {color_name.upper()}")
        self._publisher.set_roi_enabled(False)

        hsv_pixels: list[np.ndarray] = []
        lab_pixels: list[np.ndarray] = []

        async def collect_samples():
            screen.sampling = True
            await screen.refresh()
            while not screen.is_closed:
                if screen.tap_x is not None and screen.tap_y is not None:
                    frame = self._publisher.grab_frame()
                    if frame is not None:
                        pp = self._preprocess(frame)
                        hsv = self._sample_roi_at(pp, screen.tap_x, screen.tap_y)
                        lab = self._sample_roi_lab_at(pp, screen.tap_x, screen.tap_y)
                        if hsv is not None and lab is not None:
                            hsv_pixels.append(hsv)
                            lab_pixels.append(lab)
                            combined = np.vstack(hsv_pixels)
                            screen.h_mean = float(np.mean(combined[:, 0]))
                            screen.s_mean = float(np.mean(combined[:, 1]))
                            screen.v_mean = float(np.mean(combined[:, 2]))
                            screen.sample_count = len(hsv_pixels)
                            await screen.refresh()
                await asyncio.sleep(0.15)

        task = asyncio.create_task(collect_samples())
        confirmed = await self.show(screen)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        if not confirmed or len(hsv_pixels) < MIN_SAMPLE_FRAMES:
            return None

        return self._ColorSamples(hsv=hsv_pixels, lab=lab_pixels)

    @dataclass
    class _BaselineSamples:
        raw_frame: np.ndarray | None  # raw BGR frame for noise measurement
        hsv: np.ndarray | None
        lab: np.ndarray | None

    async def _sample_baseline(self) -> _BaselineSamples:
        """Capture a single background frame when the user confirms."""
        screen = BaselineScreen()
        self._publisher.set_overlay("BASELINE - remove drums")
        self._publisher.set_roi_enabled(False)

        await self.show(screen)

        # Grab a single frame at the moment the user clicks confirm
        frame = self._publisher.grab_frame()
        if frame is not None:
            pp = self._preprocess(frame)
            return self._BaselineSamples(
                raw_frame=frame,
                hsv=self._sample_full_frame(pp),
                lab=self._sample_full_frame_lab(pp),
            )
        return self._BaselineSamples(raw_frame=None, hsv=None, lab=None)

    # -- CalibrateStep hooks -------------------------------------------------

    def _compute_calibration(
        self,
        blue_samples: _ColorSamples | None,
        pink_samples: _ColorSamples | None,
        baseline: _BaselineSamples,
    ) -> ColorCalibration:
        """Compute LAB ranges + saturation gates for both colors."""
        lab_margin = dict(h_margin=10, s_margin=15, v_margin=20)  # L, a*, b*

        self.info("Computing blue ranges (LAB)...")
        blue_lab_ranges = []
        blue_sat_min = 0
        if blue_samples:
            lab_combined = np.vstack(blue_samples.lab)
            blue_lab_ranges = [self._compute_range(
                lab_combined, baseline.lab, **lab_margin,
            )]
            hsv_combined = np.vstack(blue_samples.hsv)
            sat_values = hsv_combined[:, 1].astype(float)
            blue_sat_min = max(30, int(np.percentile(sat_values, 2)) - 10)
            self.info(f"  Blue saturation gate: S >= {blue_sat_min}")

        self.info("Computing pink ranges (LAB)...")
        pink_lab_ranges = []
        pink_sat_min = 0
        if pink_samples:
            lab_combined = np.vstack(pink_samples.lab)
            pink_lab_ranges = [self._compute_range(
                lab_combined, baseline.lab, **lab_margin,
            )]
            hsv_combined = np.vstack(pink_samples.hsv)
            sat_values = hsv_combined[:, 1].astype(float)
            pink_sat_min = max(30, int(np.percentile(sat_values, 2)) - 10)
            self.info(f"  Pink saturation gate: S >= {pink_sat_min}")

        return ColorCalibration(
            blue_lab_ranges=blue_lab_ranges,
            blue_sat_min=blue_sat_min,
            pink_lab_ranges=pink_lab_ranges,
            pink_sat_min=pink_sat_min,
            min_area=MIN_AREA_FLOOR,
        )

    def _measure_noise_from_baseline(
        self, baseline_frame: np.ndarray, calibration: ColorCalibration,
    ) -> ColorCalibration:
        """Measure noise on the baseline frame (no drums) and set min_area."""
        has_ranges = calibration.blue_lab_ranges or calibration.pink_lab_ranges
        if not has_ranges:
            return calibration

        worst_noise = 0
        if calibration.blue_lab_ranges:
            area = self._measure_noise_area(
                baseline_frame, calibration.blue_lab_ranges,
                color_space="lab", sat_min=calibration.blue_sat_min,
            )
            worst_noise = max(worst_noise, area)
        if calibration.pink_lab_ranges:
            area = self._measure_noise_area(
                baseline_frame, calibration.pink_lab_ranges,
                color_space="lab", sat_min=calibration.pink_sat_min,
            )
            worst_noise = max(worst_noise, area)

        calibration.min_area = max(int(worst_noise * 2) + 100, MIN_AREA_FLOOR)
        self.info(f"Noise check: worst={worst_noise}px, min_area={calibration.min_area}px")
        return calibration

    async def _collect(self, robot: GenericRobot) -> ColorCalibration | None:
        self._start_publisher()
        try:
            self._publisher.set_overlay("Color Calibration")

            # Phase 1 & 2: tap on drums to sample colors
            blue_samples = await self._sample_color(
                "blue", "Place BLUE drum, tap on it",
            )
            pink_samples = await self._sample_color(
                "pink", "Place PINK drum, tap on it",
            )

            if blue_samples is None and pink_samples is None:
                return None

            # Phase 3: sample empty background (single frame on confirm)
            baseline = await self._sample_baseline()

            # Compute ranges and measure noise on the baseline frame
            calibration = self._compute_calibration(blue_samples, pink_samples, baseline)
            if baseline.raw_frame is not None:
                calibration = self._measure_noise_from_baseline(
                    baseline.raw_frame, calibration,
                )

            # Retry loop: allow retrying individual colors without restarting
            while True:
                result = await self._show_confirm(calibration)

                if result == "confirm":
                    return calibration
                elif result == "retry_all":
                    return None  # base class will call _collect again
                elif result == "retry_blue":
                    blue_samples = await self._sample_color(
                        "blue", "Place BLUE drum, tap on it",
                    )
                    calibration = self._compute_calibration(
                        blue_samples, pink_samples, baseline,
                    )
                    if baseline.raw_frame is not None:
                        calibration = self._measure_noise_from_baseline(
                            baseline.raw_frame, calibration,
                        )
                elif result == "retry_pink":
                    pink_samples = await self._sample_color(
                        "pink", "Place PINK drum, tap on it",
                    )
                    calibration = self._compute_calibration(
                        blue_samples, pink_samples, baseline,
                    )
                    if baseline.raw_frame is not None:
                        calibration = self._measure_noise_from_baseline(
                            baseline.raw_frame, calibration,
                        )

        except Exception:
            self._stop_publisher()
            raise

    async def _show_confirm(self, calibration: ColorCalibration) -> str:
        """Show confirm screen and return the user's choice."""
        blue_display = calibration.blue_lab_ranges[0] if calibration.blue_lab_ranges else None
        pink_display = calibration.pink_lab_ranges or None

        screen = ColorConfirmScreen(
            blue_range=blue_display,
            blue_sat_min=calibration.blue_sat_min,
            pink_ranges=pink_display,
            pink_sat_min=calibration.pink_sat_min,
            min_area=calibration.min_area,
        )
        return await self.show(screen)

    async def _confirm(
        self, robot: GenericRobot, calibration: ColorCalibration,
    ) -> tuple[bool, ColorCalibration]:
        # Confirm screen is already handled inside _collect's retry loop.
        # If we get here, the user confirmed — run the live test.
        await self._run_test(robot, calibration)

        # Stop publisher before returning — its Transport's background
        # LCM subscriptions must be cleaned up before the next UIStep
        # tries to use the same channels.
        self._stop_publisher()
        await self.close_ui()

        return True, calibration

    async def _run_test(
        self, robot: GenericRobot, calibration: ColorCalibration,
    ) -> None:
        """Live test phase: detect colors and show results."""
        screen = ColorTestScreen()
        self._publisher.set_overlay("TEST MODE - place drum")

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
        calibration: ColorCalibration,
    ) -> tuple[str | None, float, list[dict]]:
        """Run single-frame color detection matching the runtime pipeline."""
        pp = self._preprocess(frame)
        hsv = cv2.cvtColor(pp, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(pp, cv2.COLOR_BGR2LAB)
        h, w = frame.shape[:2]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        best_color = None
        best_area = 0
        detections = []

        for name, lab_ranges, sat_min in [
            ("blue", calibration.blue_lab_ranges, calibration.blue_sat_min),
            ("pink", calibration.pink_lab_ranges, calibration.pink_sat_min),
        ]:
            if not lab_ranges:
                continue
            mask = None
            for lower, upper in lab_ranges:
                m = cv2.inRange(lab, np.array(lower), np.array(upper))
                mask = m if mask is None else cv2.bitwise_or(mask, m)
            if mask is None:
                continue
            if sat_min > 0:
                sat_mask = (hsv[:, :, 1] >= sat_min).astype(np.uint8) * 255
                mask = cv2.bitwise_and(mask, sat_mask)
            det = self._contour_detect(mask, kernel, name, w, h, calibration.min_area)
            if det:
                detections.append(det)
                if det["area"] > best_area:
                    best_area = det["area"]
                    best_color = name

        confidence = min(best_area / 5000.0, 1.0) if best_color else 0.0
        return best_color, confidence, detections

    @staticmethod
    def _contour_detect(
        mask: np.ndarray, kernel: np.ndarray,
        label: str, w: int, h: int, min_area: int,
    ) -> dict | None:
        """Find largest contour in mask and return detection dict or None."""
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        area = int(cv2.contourArea(largest))
        if area < min_area:
            return None
        x, y, bw, bh = cv2.boundingRect(largest)
        return {
            "label": label,
            "x": (x + bw / 2) / w,
            "y": (y + bh / 2) / h,
            "width": bw / w,
            "height": bh / h,
            "area": area,
            "confidence": min(area / 5000.0, 1.0),
        }

    def _apply(self, robot: GenericRobot, calibration: ColorCalibration) -> None:
        from src.service.color_detection_service import ColorDetectionService

        service = robot.get_service(ColorDetectionService)
        service.apply_calibration(
            blue_lab_ranges=calibration.blue_lab_ranges,
            blue_sat_min=calibration.blue_sat_min,
            pink_lab_ranges=calibration.pink_lab_ranges,
            pink_sat_min=calibration.pink_sat_min,
            min_area=calibration.min_area,
        )
        self.info("Color calibration applied to detection service")

    def _serialize(self, calibration: ColorCalibration) -> dict:
        return {
            "blue_lab_ranges": [
                [list(lo), list(hi)] for lo, hi in calibration.blue_lab_ranges
            ],
            "blue_sat_min": calibration.blue_sat_min,
            "pink_lab_ranges": [
                [list(lo), list(hi)] for lo, hi in calibration.pink_lab_ranges
            ],
            "pink_sat_min": calibration.pink_sat_min,
            "min_area": calibration.min_area,
        }

    def _deserialize(self, data: dict) -> ColorCalibration:
        return ColorCalibration(
            blue_lab_ranges=[
                (tuple(lo), tuple(hi)) for lo, hi in data.get("blue_lab_ranges", [])
            ],
            blue_sat_min=int(data.get("blue_sat_min", 0)),
            pink_lab_ranges=[
                (tuple(lo), tuple(hi)) for lo, hi in data.get("pink_lab_ranges", [])
            ],
            pink_sat_min=int(data.get("pink_sat_min", 0)),
            min_area=data.get("min_area", MIN_AREA_FLOOR),
        )


@dsl()
def calibrate_colors(
    camera_index: int | str = "/dev/video0",
    resolution: tuple[int, int] = (160, 120),
) -> ColorCalibrationStep:
    """Interactive HSV color calibration for drum detection."""
    return ColorCalibrationStep(
        camera_index=camera_index,
        resolution=resolution,
    )
