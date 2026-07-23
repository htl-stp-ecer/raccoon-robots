"""Standalone image analysis helpers for color calibration.

All functions are pure (frame in, result out) with no robot/service state.
"""

import os
from dataclasses import dataclass

import cv2
import numpy as np

SAT_GATE_MIN_PIXELS = 150  # min pixels surviving morphological opening to pass gate
SAT_GATE_KERNEL = 9        # opening kernel side (px)
SAT_COARSE_THRESH = 40     # low fixed threshold used to find blobs during calibration


@dataclass
class ColorCalibration:
    sat_threshold: int = 50


def dominant_blob(frame: np.ndarray) -> tuple[int, int]:
    """Return (mean_sat, blob_area) of the dominant large saturated blob.

    Uses morphological opening at a low coarse threshold to eliminate small
    objects (lego pieces etc.) before finding the largest blob.
    Returns (0, 0) when no blob survives (e.g. empty background frame).
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    coarse = (sat >= SAT_COARSE_THRESH).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (SAT_GATE_KERNEL, SAT_GATE_KERNEL))
    cleaned = cv2.morphologyEx(coarse, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0, 0
    largest = max(contours, key=cv2.contourArea)
    blob_area = int(cv2.contourArea(largest))
    blob_mask = np.zeros(sat.shape, dtype=np.uint8)
    cv2.drawContours(blob_mask, [largest], -1, 255, cv2.FILLED)
    return int(sat[blob_mask == 255].mean()), blob_area


def compute_threshold(blue_sat: int, pink_sat: int, empty_sat: int) -> int:
    """Midpoint between the empty max and the lower of the two drum maxes."""
    return (empty_sat + min(blue_sat, pink_sat)) // 2


def detect_color_from_frame(
    frame: np.ndarray,
    calibration: ColorCalibration,
) -> tuple[str | None, float, list[dict]]:
    """Single-frame color detection matching the runtime pipeline."""
    h, w = frame.shape[:2]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    gate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (SAT_GATE_KERNEL, SAT_GATE_KERNEL))

    hsv_raw = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    sat_mask_raw = (hsv_raw[:, :, 1] >= calibration.sat_threshold).astype(np.uint8) * 255
    sat_mask_opened = cv2.morphologyEx(sat_mask_raw, cv2.MORPH_OPEN, gate_kernel)
    if int((sat_mask_opened > 0).sum()) < SAT_GATE_MIN_PIXELS:
        return None, 0.0, []

    avg = frame.mean(axis=(0, 1))
    pp = np.clip(frame * (avg.mean() / (avg + 1e-6)), 0, 255).astype(np.uint8)
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
    color = "pink" if float(lab[:, :, 1][contour_mask == 255].mean()) > 128 else "blue"

    confidence = min(area / 2000.0, 1.0)
    detection = {
        "label": color,
        "x": (x + bw / 2) / w, "y": (y + bh / 2) / h,
        "width": bw / w, "height": bh / h,
        "area": area, "confidence": confidence,
    }
    return color, confidence, [detection]


def save_debug_mask(
    frames: dict[str, np.ndarray],
    threshold: int,
    path: str = "sat_debug.png",
) -> None:
    """Save a side-by-side PNG: original | sat channel | raw mask | opened mask per frame."""
    gate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (SAT_GATE_KERNEL, SAT_GATE_KERNEL))
    rows = []
    for label, frame in frames.items():
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        mask_raw = (sat >= threshold).astype(np.uint8) * 255
        mask_opened = cv2.morphologyEx(mask_raw, cv2.MORPH_OPEN, gate_kernel)
        count = int((mask_opened > 0).sum())
        passes_gate = count >= SAT_GATE_MIN_PIXELS

        tinted = frame.copy()
        tint_color = (0, 200, 0) if passes_gate else (0, 0, 200)
        tinted[mask_opened > 0] = (
            np.clip(tinted[mask_opened > 0].astype(int) // 2 + np.array(tint_color) // 2, 0, 255)
            .astype(np.uint8)
        )

        row = np.hstack([
            tinted,
            cv2.cvtColor(sat, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(mask_raw, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(mask_opened, cv2.COLOR_GRAY2BGR),
        ])
        blob_sat, blob_area = dominant_blob(frame)
        tag = (
            f"{label.upper()}  blob_sat={blob_sat}  blob_area={blob_area}  "
            f"thresh={threshold}  opened_px={count}  "
            f"{'PASS' if passes_gate else 'FAIL'}(min={SAT_GATE_MIN_PIXELS})"
        )
        cv2.putText(row, tag, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(row, tag, (3, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        rows.append(row)

    cv2.imwrite(os.path.abspath(path), np.vstack(rows))


def save_debug_frame(frame: np.ndarray, path: str = "debug_frame.png") -> None:
    """Save a raw camera frame for visual inspection."""
    cv2.imwrite(os.path.abspath(path), frame)
