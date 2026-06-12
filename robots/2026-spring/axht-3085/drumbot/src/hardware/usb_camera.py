"""
USB camera module for color blob detection.

Provides configurable color profiles with multi-frame consensus analysis,
designed for RPi3 performance constraints.
"""

import os
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from statistics import median
from typing import Callable

import cv2
import numpy as np
from raccoon import debug, error, info, warn


@dataclass
class ColorProfile:
    """A named color used by the chroma-based detector.

    The legacy ``hsv_ranges`` / ``lab_ranges`` / ``sat_min`` fields are kept so
    existing callers (and persisted configs) don't break, but the runtime only
    uses ``name``, ``min_area`` and ``min_dimension``. Per-color hue thresholds
    are global on the camera (``pink_a_min``, ``blue_b_max``) — they are
    intrinsic to the CIELAB axes and don't need per-instance tuning.
    """

    name: str
    hsv_ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = field(default_factory=list)
    min_area: int = 900
    min_dimension: int = 20
    lab_ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]] | None = None
    sat_min: int = 0


@dataclass
class BlobResult:
    """Single-frame detection result for one color."""

    present: bool
    area: int = 0
    bounding_box: tuple[int, int, int, int] = (0, 0, 0, 0)
    center: tuple[int, int] = (0, 0)


@dataclass
class ColorConsensus:
    """Multi-frame consensus for one color."""

    present: bool
    confidence: float = 0.0
    median_area: int = 0
    median_center: tuple[int, int] = (0, 0)
    median_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class AnalysisResult:
    """Aggregated analysis across all registered colors."""

    colors: dict[str, ColorConsensus] = field(default_factory=dict)
    frames_analyzed: int = 0
    timestamp: float = 0.0

    def is_present(self, name: str) -> bool:
        consensus = self.colors.get(name)
        return consensus.present if consensus else False

    def get(self, name: str) -> ColorConsensus | None:
        return self.colors.get(name)


class USBCamera:
    """USB camera with background capture and on-demand color blob analysis."""

    def __init__(
        self,
        camera_index: int | str = 0,
        resolution: tuple[int, int] = (320, 240),
        buffer_size: int = 30,
        capture_fps: int = 15,
        presence_threshold: float = 0.5,
        morph_kernel_size: int = 3,
        save_frames: bool = False,
        frames_dir: str = "frames",
        get_time: Callable[[], float] | None = None,
        codec: str = "MJPG",
    ):
        self._camera_index = camera_index
        self._resolution = resolution
        self._buffer_size = buffer_size
        self._capture_fps = capture_fps
        self._codec = codec
        self._presence_threshold = presence_threshold
        self._morph_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size)
        )

        # CIELAB chroma detector tunables. ``chroma_threshold`` is the only
        # value the calibration step learns from the empty background; the
        # hue-axis thresholds and the L* clip are intrinsic and stay constant.
        # See _analyze_frame for the geometry.
        self._chroma_threshold: int = 25
        self._pink_a_min: int = 18
        self._blue_b_max: int = -18
        self._l_min: int = 25     # ignore deep shadows
        self._l_max: int = 240    # ignore specular highlights on glossy drums
        self._colors: dict[str, ColorProfile] = {}
        self._buffer: deque[np.ndarray] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._cap: cv2.VideoCapture | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._total_frames: int = 0

        self._save_frames = save_frames
        self._frames_dir = frames_dir
        self._get_time = get_time
        self._io_pool: ThreadPoolExecutor | None = None
        self._frame_count = 0

    def add_color(
        self,
        name: str,
        hsv_ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]] | None = None,
        min_area: int = 900,
        min_dimension: int = 20,
        lab_ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]] | None = None,
        sat_min: int = 0,
    ) -> None:
        """Register a color profile for detection.

        Only ``name``, ``min_area`` and ``min_dimension`` matter for the
        chroma-based detector; the other arguments are accepted for
        backwards compatibility with old call sites.
        """
        self._colors[name] = ColorProfile(
            name=name,
            hsv_ranges=hsv_ranges or [],
            min_area=min_area,
            min_dimension=min_dimension,
            lab_ranges=lab_ranges,
            sat_min=sat_min,
        )
        debug(f"Registered color '{name}' (chroma detector, min_area={min_area})")

    def remove_color(self, name: str) -> None:
        """Remove a registered color profile."""
        self._colors.pop(name, None)

    def set_chroma_threshold(self, value: int) -> None:
        """Set the global CIELAB chroma threshold used in _analyze_frame.

        Chroma = sqrt((a-128)^2 + (b-128)^2). Neutral gray pixels have
        chroma ~ 0; the empty background sits low (5..20 typical), drum
        surfaces sit high (40..100). Calibration learns this value from
        the empty-background sample.
        """
        self._chroma_threshold = int(value)

    # Back-compat alias: previously the camera exposed a saturation gate.
    # Kept so unrelated callers don't blow up if they still call it.
    set_sat_threshold = set_chroma_threshold

    def start(self, open_retries: int = 5, retry_delay: float = 1.0) -> "USBCamera":
        """Open the camera and start the background capture thread."""
        if self._running:
            warn("Camera is already running")
            return self

        for attempt in range(1, open_retries + 1):
            self._cap = cv2.VideoCapture(self._camera_index, cv2.CAP_V4L2)
            if self._cap.isOpened():
                break
            self._cap.release()
            self._cap = None
            if attempt < open_retries:
                warn(
                    f"Could not open camera at index {self._camera_index} "
                    f"(attempt {attempt}/{open_retries}), retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
        else:
            error(f"Could not open camera at index {self._camera_index} after {open_retries} attempts")
            raise RuntimeError(
                f"Could not open camera at index {self._camera_index}",
            )

        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._codec))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
        self._cap.set(cv2.CAP_PROP_FPS, self._capture_fps)

        if self._save_frames:
            os.makedirs(self._frames_dir, exist_ok=True)
            self._io_pool = ThreadPoolExecutor(max_workers=1)

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        info(
            f"Camera started (index={self._camera_index}, "
            f"res={self._resolution}, fps={self._capture_fps})"
        )
        return self

    def stop(self) -> None:
        """Stop the capture thread and release the camera."""
        if not self._running:
            return

        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._io_pool is not None:
            self._io_pool.shutdown(wait=True)
            self._io_pool = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        info("Camera stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def buffer_count(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def total_frames(self) -> int:
        return self._total_frames

    def clear_buffer(self) -> None:
        with self._lock:
            self._buffer.clear()

    def __enter__(self) -> "USBCamera":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    def _save_frame(self, frame: np.ndarray, sync_time: float, seq: int) -> None:
        """Annotate and write a frame to disk."""
        label = f"t={sync_time:.2f}s"
        annotated = frame.copy()
        cv2.putText(
            annotated,
            label,
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        path = os.path.join(self._frames_dir, f"frame_{seq:04d}_t{sync_time:.2f}s.jpg")
        cv2.imwrite(path, annotated)

    def _capture_loop(self) -> None:
        interval = 1.0 / self._capture_fps
        fps_window_start = time.monotonic()
        fps_frame_count = 0
        while self._running:
            t0 = time.monotonic()
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._buffer.append(frame)
                self._total_frames += 1
                fps_frame_count += 1
                if self._save_frames and self._io_pool is not None:
                    self._frame_count += 1
                    sync_time = self._get_time() if self._get_time else 0.0
                    self._io_pool.submit(self._save_frame, frame, sync_time, self._frame_count)
            else:
                warn("Failed to capture frame")

            fps_elapsed = t0 - fps_window_start
            if fps_elapsed >= 5.0:
                actual_fps = fps_frame_count / fps_elapsed
                info(f"Camera FPS: {actual_fps:.1f} (target {self._capture_fps})")
                fps_window_start = t0
                fps_frame_count = 0

            elapsed = time.monotonic() - t0
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def grab_frame(self) -> np.ndarray | None:
        """Return the most recent frame, or None if buffer is empty."""
        with self._lock:
            return self._buffer[-1].copy() if self._buffer else None

    def grab_frames(self, count: int) -> list[np.ndarray]:
        """Return copies of the most recent ``count`` frames, oldest first."""
        with self._lock:
            frames = list(self._buffer)[-max(0, count):]
        return [frame.copy() for frame in frames]

    def get_annotated_debug_frame(self, frame: np.ndarray) -> np.ndarray:
        """Return an annotated copy of ``frame`` visualising the chroma detector.

        Overlays:
        - Pink mask tinted magenta, blue mask tinted cyan.
        - Bounding boxes around each detected blob with label/area/mean chroma.
        - Text panel with the active chroma threshold and per-pixel chroma stats.
        """
        annotated = frame.copy()
        L, a_s, b_s, chroma, valid_L = self._chroma_planes(frame)

        max_c = float(chroma.max())
        cv2.putText(
            annotated,
            f"C_thresh={self._chroma_threshold} max_C={max_c:.0f}",
            (4, 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        pink_mask, blue_mask = self._build_color_masks(a_s, b_s, chroma, valid_L)

        # Tint detected pixels for visual feedback.
        overlay = annotated.copy()
        overlay[pink_mask == 255] = (180, 80, 255)   # magenta-ish BGR
        overlay[blue_mask == 255] = (255, 150, 0)    # cyan-ish BGR
        cv2.addWeighted(overlay, 0.4, annotated, 0.6, 0, annotated)

        first_profile = next(iter(self._colors.values())) if self._colors else None
        min_area = first_profile.min_area if first_profile else 500
        min_dim = first_profile.min_dimension if first_profile else 5

        for label, mask in (("pink", pink_mask), ("blue", blue_mask)):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            largest = max(contours, key=cv2.contourArea)
            area = int(cv2.contourArea(largest))
            x, y, bw, bh = cv2.boundingRect(largest)
            size_ok = area >= min_area and bw >= min_dim and bh >= min_dim
            draw_bgr = (180, 80, 255) if label == "pink" else (255, 150, 0)
            rect_color = (0, 0, 200) if not size_ok else draw_bgr
            cv2.drawContours(annotated, [largest], -1, draw_bgr, 1)
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), rect_color, 2)

            contour_mask = np.zeros(mask.shape, dtype=np.uint8)
            cv2.drawContours(contour_mask, [largest], -1, 255, cv2.FILLED)
            pix = contour_mask == 255
            mean_c = float(chroma[pix].mean()) if pix.any() else 0.0
            tag = f"{label} C={mean_c:.0f} area={area}"
            cv2.putText(
                annotated,
                tag,
                (x, max(y - 4, 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                draw_bgr,
                1,
                cv2.LINE_AA,
            )
            if not size_ok:
                cv2.putText(
                    annotated,
                    f"TOO SMALL ({bw}x{bh})",
                    (x, y + bh + 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.38,
                    (0, 0, 255),
                    1,
                    cv2.LINE_AA,
                )

        return annotated

    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        """Light Gaussian blur — no white balance.

        Gray-world WB destroys color information when the drum fills the
        frame (pink → green, blue → yellow), which is exactly the case
        during calibration. CIELAB chroma is already largely invariant to
        the camera's white point, so blur is all we need.
        """
        return cv2.GaussianBlur(frame, (3, 3), 0)

    def _chroma_planes(
        self, frame: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return (L, a_s, b_s, chroma, valid_L) for a BGR frame.

        ``a_s = a - 128`` and ``b_s = b - 128`` are signed CIELAB hue
        components in roughly [-128, 127]. ``chroma`` is their L2 norm.
        ``valid_L`` masks pixels whose lightness is in the usable band —
        glossy specular highlights and deep shadows are excluded.
        """
        blurred = self._preprocess(frame)
        lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
        L = lab[:, :, 0]
        a_s = lab[:, :, 1].astype(np.int16) - 128
        b_s = lab[:, :, 2].astype(np.int16) - 128
        chroma = np.sqrt(a_s.astype(np.float32) ** 2 + b_s.astype(np.float32) ** 2)
        valid_L = (L >= self._l_min) & (L <= self._l_max)
        return L, a_s, b_s, chroma, valid_L

    def _build_color_masks(
        self,
        a_s: np.ndarray,
        b_s: np.ndarray,
        chroma: np.ndarray,
        valid_L: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build morphologically-cleaned pink and blue masks."""
        chromatic = (chroma > self._chroma_threshold) & valid_L
        pink = (chromatic & (a_s > self._pink_a_min)).astype(np.uint8) * 255
        blue = (chromatic & (b_s < self._blue_b_max)).astype(np.uint8) * 255
        pink = cv2.morphologyEx(pink, cv2.MORPH_OPEN, self._morph_kernel)
        pink = cv2.morphologyEx(pink, cv2.MORPH_CLOSE, self._morph_kernel)
        blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, self._morph_kernel)
        blue = cv2.morphologyEx(blue, cv2.MORPH_CLOSE, self._morph_kernel)
        return pink, blue

    def chroma_stats(self, frame: np.ndarray) -> dict[str, float]:
        """Return summary chroma/hue statistics for a single frame.

        Used by the calibration step to learn the chroma threshold from
        empty-background frames and to sanity-check drum samples.
        """
        _, a_s, b_s, chroma, valid_L = self._chroma_planes(frame)
        valid = valid_L
        chroma_v = chroma[valid]
        a_v = a_s[valid]
        b_v = b_s[valid]
        if chroma_v.size == 0:
            return {
                "median_chroma": 0.0,
                "p95_chroma": 0.0,
                "max_chroma": 0.0,
                "mean_a_chromatic": 0.0,
                "mean_b_chromatic": 0.0,
                "chromatic_fraction": 0.0,
            }
        chromatic = chroma_v > self._chroma_threshold
        n_chrom = int(chromatic.sum())
        return {
            "median_chroma": float(np.median(chroma_v)),
            "p95_chroma": float(np.percentile(chroma_v, 95)),
            "max_chroma": float(chroma_v.max()),
            "mean_a_chromatic": float(a_v[chromatic].mean()) if n_chrom else 0.0,
            "mean_b_chromatic": float(b_v[chromatic].mean()) if n_chrom else 0.0,
            "chromatic_fraction": n_chrom / chroma_v.size,
        }

    def _analyze_frame(self, frame: np.ndarray) -> dict[str, BlobResult]:
        """Detect blue/pink blobs using CIELAB chroma.

        Pipeline:
          1. Convert to LAB, compute chroma and valid-L mask (drops
             specular highlights on glossy drums and deep shadows).
          2. Build two separate masks via hue-axis signs on (a-128, b-128).
          3. Pick the largest contour per mask, gated by min area/dim.
          4. If both colors trigger (e.g. a multi-color reflection), keep
             the one with the larger area — the drum is a single object.
        """
        absent = {name: BlobResult(present=False) for name in self._colors}
        if not self._colors:
            return absent

        _, a_s, b_s, chroma, valid_L = self._chroma_planes(frame)
        pink_mask, blue_mask = self._build_color_masks(a_s, b_s, chroma, valid_L)

        first_profile = next(iter(self._colors.values()))
        min_area = first_profile.min_area
        min_dim = first_profile.min_dimension

        results = absent.copy()
        for label, mask in (("pink", pink_mask), ("blue", blue_mask)):
            if label not in self._colors:
                continue
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            largest = max(contours, key=cv2.contourArea)
            area = int(cv2.contourArea(largest))
            x, y, w, h = cv2.boundingRect(largest)
            if area < min_area or w < min_dim or h < min_dim:
                continue
            results[label] = BlobResult(
                present=True,
                area=area,
                bounding_box=(x, y, w, h),
                center=(x + w // 2, y + h // 2),
            )

        if results.get("pink", BlobResult(False)).present and results.get("blue", BlobResult(False)).present:
            if results["pink"].area >= results["blue"].area:
                results["blue"] = BlobResult(present=False)
            else:
                results["pink"] = BlobResult(present=False)

        return results

    def analyze(
        self,
        last_n_frames: int | None = None,
        presence_threshold: float | None = None,
    ) -> AnalysisResult:
        """Analyze buffered frames and return consensus results."""
        if not self._colors:
            warn("No colors registered, nothing to analyze")
            return AnalysisResult(timestamp=time.time())

        threshold = (
            presence_threshold
            if presence_threshold is not None
            else self._presence_threshold
        )

        with self._lock:
            frames = list(self._buffer)

        if last_n_frames is not None and last_n_frames < len(frames):
            frames = frames[-last_n_frames:]

        if not frames:
            warn("No frames in buffer to analyze")
            return AnalysisResult(timestamp=time.time())

        per_frame: list[dict[str, BlobResult]] = [self._analyze_frame(f) for f in frames]

        n = len(per_frame)
        consensus: dict[str, ColorConsensus] = {}

        for name in self._colors:
            detections = [r[name] for r in per_frame if name in r and r[name].present]
            confidence = len(detections) / n
            present = confidence >= threshold

            if not detections:
                consensus[name] = ColorConsensus(present=False, confidence=confidence)
                continue

            areas = [d.area for d in detections]
            cxs = [d.center[0] for d in detections]
            cys = [d.center[1] for d in detections]
            bxs = [d.bounding_box[0] for d in detections]
            bys = [d.bounding_box[1] for d in detections]
            bws = [d.bounding_box[2] for d in detections]
            bhs = [d.bounding_box[3] for d in detections]

            consensus[name] = ColorConsensus(
                present=present,
                confidence=confidence,
                median_area=int(median(areas)),
                median_center=(int(median(cxs)), int(median(cys))),
                median_bbox=(
                    int(median(bxs)),
                    int(median(bys)),
                    int(median(bws)),
                    int(median(bhs)),
                ),
            )

        debug(
            f"Analyzed {n} frames: "
            + ", ".join(
                f"{name}={'present' if c.present else 'absent'}({c.confidence:.0%})"
                for name, c in consensus.items()
            )
        )

        return AnalysisResult(colors=consensus, frames_analyzed=n, timestamp=time.time())
