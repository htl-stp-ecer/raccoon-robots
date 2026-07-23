"""Interactive color calibration backed by the vision daemon.

The setup UI still shows the live ``CamFeed``, but frame capture and OpenCV
analysis now happen in ``src.daemons.vision``. The calibration we learn here
is the CIELAB *chroma* threshold above which a pixel counts as "colored". The
empty-background sample sets the floor; the drum samples are then **replayed
through the live detector** to verify the threshold actually works on real
camera output instead of relying on indirect p95-vs-p95 comparisons.
"""

from __future__ import annotations

import asyncio
import glob
import os
from dataclasses import dataclass

import cv2

from raccoon import GenericRobot, dsl, run
from raccoon.step.calibration import CalibrateStep

from src.hardware.usb_camera import USBCamera
from src.service.color_detection_service import ColorDetectionService

from .screens import (
    BaselineScreen,
    ColorCapturingScreen,
    ColorConfirmScreen,
    ColorTestScreen,
)

CONFIDENCE_THRESHOLD = 0.9

# Safety margin (in CIELAB chroma units) added on top of the empty
# background's p95 chroma to pick the runtime threshold. 8 is large enough
# to comfortably clear sensor noise on a slightly-tinted background while
# staying far below typical drum-surface chroma (40..100).
EMPTY_MARGIN = 8
# Absolute floor — never trust a chroma threshold below this. Pixel noise
# can briefly push individual pixels to ~15 even on a neutral background.
MIN_CHROMA_THRESHOLD = 18
# Minimum per-color detection rate on the captured calibration frames.
# The detector must label this fraction of the blue frames as "blue", of the
# pink frames as "pink", and of the empty frames as "no drum". Anything less
# and we refuse to commit the calibration.
MIN_DETECTION_RATE = 0.9


@dataclass(frozen=True)
class ColorCalibration:
    chroma_threshold: int


def compute_threshold(empty_p95: float) -> int:
    return max(MIN_CHROMA_THRESHOLD, int(round(empty_p95 + EMPTY_MARGIN)))


def _classify_dir(cam: USBCamera, directory: str) -> dict[str, int]:
    """Replay every PNG in ``directory`` through the live detector.

    Returns a counter of ``{"blue": n, "pink": n, "none": n}`` so we can
    compute per-label detection rates from the actually-captured frames.
    """
    counts = {"blue": 0, "pink": 0, "none": 0}
    for path in sorted(glob.glob(os.path.join(directory, "frame_*.png"))):
        frame = cv2.imread(path)
        if frame is None:
            continue
        results = cam._analyze_frame(frame)  # noqa: SLF001 — same-package call
        present = [name for name, blob in results.items() if blob.present]
        if not present:
            counts["none"] += 1
        else:
            counts[max(present, key=lambda n: results[n].area)] += 1
    return counts


def _verify_threshold(
    chroma_threshold: int,
    empty_dir: str,
    blue_dir: str,
    pink_dir: str,
) -> tuple[bool, dict[str, dict[str, int]]]:
    """Re-run the live detector on the captured frames at ``chroma_threshold``.

    Returns (passed, per-label counts). The threshold is accepted iff each
    label hits ``MIN_DETECTION_RATE`` of its expected class.
    """
    cam = USBCamera()
    cam.set_chroma_threshold(chroma_threshold)
    cam.add_color("blue", min_area=500, min_dimension=5)
    cam.add_color("pink", min_area=500, min_dimension=5)

    counts = {
        "empty": _classify_dir(cam, empty_dir),
        "blue": _classify_dir(cam, blue_dir),
        "pink": _classify_dir(cam, pink_dir),
    }

    def rate(label: str, expected: str) -> float:
        n = sum(counts[label].values())
        return counts[label][expected] / n if n else 0.0

    ok = (
        rate("empty", "none") >= MIN_DETECTION_RATE
        and rate("blue", "blue") >= MIN_DETECTION_RATE
        and rate("pink", "pink") >= MIN_DETECTION_RATE
    )
    return ok, counts


class ColorCalibrationStep(CalibrateStep[ColorCalibration]):
    def __init__(self):
        super().__init__(store_section="color-detection", store_set="default")

    async def _capture_sample(
        self,
        robot: GenericRobot,
        instruction: str,
        badge: str,
        label: str,
    ) -> dict | None:
        service = robot.get_service(ColorDetectionService)
        service.set_overlay(instruction)
        screen = BaselineScreen(instruction=instruction, badge=badge)
        confirmed = await self.show(screen)
        if not confirmed:
            return None

        async def capture() -> dict | None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: service.capture_calibration_sample(label),
            )

        return await self.run_with_ui(
            ColorCapturingScreen(instruction=instruction, badge=badge),
            capture,
        )

    async def _collect(self, robot: GenericRobot) -> ColorCalibration | None:
        blue = await self._capture_sample(robot, "Place BLUE drum in view", "BLUE", "blue")
        pink = await self._capture_sample(robot, "Place PINK drum in view", "PINK", "pink")
        empty = await self._capture_sample(robot, "Remove all drums", "EMPTY", "empty")

        if blue is None or pink is None or empty is None:
            self.warn("Missing samples - retrying calibration")
            await asyncio.sleep(0.3)
            return None

        # Use p95 for both ends. The drum usually does NOT fill the frame,
        # so a median over all pixels is dominated by background and tells
        # us nothing — p95 captures the top 5 % of pixels, which is where
        # the actual drum surface lives.
        empty_p95 = float(empty["p95_chroma"])
        blue_p95 = float(blue["p95_chroma"])
        pink_p95 = float(pink["p95_chroma"])
        threshold = compute_threshold(empty_p95)
        blue_frac = float(blue.get("chromatic_fraction", 0.0))
        pink_frac = float(pink.get("chromatic_fraction", 0.0))
        empty_frac = float(empty.get("chromatic_fraction", 0.0))
        self.info(
            f"Chroma p95: empty={empty_p95:.1f}, blue={blue_p95:.1f}, "
            f"pink={pink_p95:.1f} -> threshold={threshold}"
        )
        self.info(
            f"Chromatic fraction (pixels above current C): empty={empty_frac:.1%}, "
            f"blue={blue_frac:.1%}, pink={pink_frac:.1%}"
        )
        self.info(
            f"Sample dirs: empty={empty.get('samples_dir')}, "
            f"blue={blue.get('samples_dir')}, pink={pink.get('samples_dir')}"
        )

        # Empirical verification: replay the captured frames through the
        # live detector at the chosen threshold and require >=90 % correct
        # per label. This is a much sharper signal than comparing p95s,
        # because the detector also factors in hue, L*-validity and the
        # min_area gate.
        empty_dir = empty.get("samples_dir")
        blue_dir = blue.get("samples_dir")
        pink_dir = pink.get("samples_dir")
        if empty_dir and blue_dir and pink_dir:
            passed, counts = _verify_threshold(threshold, empty_dir, blue_dir, pink_dir)
            self.info(
                "Verification on captured frames: "
                f"empty={counts['empty']}, blue={counts['blue']}, pink={counts['pink']}"
            )
            if not passed:
                self.warn(
                    "Bad calibration: detector fails on captured frames at "
                    f"threshold={threshold}. Counts={counts}. "
                    "Drum is likely too small / lighting too dim / washed out."
                )
                await asyncio.sleep(0.3)
                return None
        else:
            self.warn("Verification skipped — sample directories missing in response")

        # Hue-axis sanity check — pink should sit on a*>0, blue on b*<0.
        if pink["mean_a_chromatic"] <= 0 or blue["mean_b_chromatic"] >= 0:
            self.warn(
                f"Drum hue axes look wrong: pink mean_a*={pink['mean_a_chromatic']:.1f}, "
                f"blue mean_b*={blue['mean_b_chromatic']:.1f}. Camera or labels swapped?"
            )

        calibration = ColorCalibration(chroma_threshold=threshold)

        while True:
            screen = ColorConfirmScreen(
                chroma_threshold=threshold,
                blue_chroma=int(round(blue_p95)),
                pink_chroma=int(round(pink_p95)),
                empty_p95_chroma=int(round(empty_p95)),
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
        service.apply_calibration(calibration.chroma_threshold)
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
        service.apply_calibration(chroma_threshold=calibration.chroma_threshold)
        self.info(f"Color calibration applied: chroma_threshold={calibration.chroma_threshold}")

    def _serialize(self, calibration: ColorCalibration) -> dict:
        return {"chroma_threshold": calibration.chroma_threshold}

    def _deserialize(self, data: dict) -> ColorCalibration:
        # Old persisted calibrations stored ``sat_threshold`` — its numeric
        # range is incompatible with the chroma detector, so ignore it and
        # fall back to a safe default. The user will re-calibrate.
        if "chroma_threshold" in data:
            return ColorCalibration(chroma_threshold=int(data["chroma_threshold"]))
        return ColorCalibration(chroma_threshold=MIN_CHROMA_THRESHOLD)


@dsl()
def calibrate_colors() -> ColorCalibrationStep:
    """Interactive chroma-threshold calibration for daemon-backed drum detection."""
    if os.getenv("DRUMBOT_FAKE_CAMERA") == "1":
        return run(lambda robot: None)
    else:
        return ColorCalibrationStep()
