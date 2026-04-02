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
from libstp import debug, error, info, warn


@dataclass
class ColorProfile:
    """A named color with HSV or LAB+saturation-gate ranges."""

    name: str
    hsv_ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]]
    min_area: int = 900
    min_dimension: int = 20
    # When set, detection uses LAB ranges + HSV saturation gate instead of hsv_ranges.
    lab_ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]] | None = None
    sat_min: int = 0


@dataclass
class BlobResult:
    """Single-frame detection result for one color."""

    present: bool
    area: int = 0
    bounding_box: tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h
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
    """USB camera with background capture and on-demand color blob analysis.

    Usage:
        camera = USBCamera()
        camera.add_color("orange", hsv_ranges=[((5, 150, 100), (15, 255, 255))])
        camera.start()
        result = camera.analyze(last_n_frames=10)
        if result.is_present("orange"):
            print(result.get("orange").median_center)
        camera.stop()
    """

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
            cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size),
        )

        self._colors: dict[str, ColorProfile] = {}
        self._buffer: deque[np.ndarray] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._cap: cv2.VideoCapture | None = None
        self._running = False
        self._disconnected = False
        self._thread: threading.Thread | None = None
        self._total_frames: int = 0

        # Frame recording
        self._save_frames = save_frames
        self._frames_dir = frames_dir
        self._get_time = get_time
        self._io_pool: ThreadPoolExecutor | None = None
        self._frame_count = 0

    # -- Color registration --------------------------------------------------

    def add_color(
        self,
        name: str,
        hsv_ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]],
        min_area: int = 900,
        min_dimension: int = 20,
        lab_ranges: list[tuple[tuple[int, int, int], tuple[int, int, int]]] | None = None,
        sat_min: int = 0,
    ) -> None:
        """Register a color profile for detection."""
        self._colors[name] = ColorProfile(
            name=name,
            hsv_ranges=hsv_ranges,
            min_area=min_area,
            min_dimension=min_dimension,
            lab_ranges=lab_ranges,
            sat_min=sat_min,
        )
        mode = "LAB+sat" if lab_ranges else "HSV"
        debug(f"Registered color '{name}' ({mode}, {len(lab_ranges or hsv_ranges)} range(s))")

    def remove_color(self, name: str) -> None:
        """Remove a registered color profile."""
        self._colors.pop(name, None)

    # -- Lifecycle ------------------------------------------------------------

    def start(self) -> "USBCamera":
        """Open the camera and start the background capture thread."""
        if self._running:
            warn("Camera is already running")
            return self

        # V4L2 sometimes holds the device briefly after a prior handle is released
        # (e.g. CamPublisher from calibration). Retry for up to ~2 s.
        import time as _time
        _retries = 10
        for _attempt in range(_retries):
            self._cap = cv2.VideoCapture(self._camera_index, cv2.CAP_V4L2)
            if self._cap.isOpened():
                break
            self._cap.release()
            if _attempt < _retries - 1:
                _time.sleep(0.2)
        if not self._cap.isOpened():
            error(f"Could not open camera at index {self._camera_index}")
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
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True,
        )
        self._thread.start()
        info(
            f"Camera started (index={self._camera_index}, "
            f"res={self._resolution}, fps={self._capture_fps})",
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
    def is_disconnected(self) -> bool:
        return self._disconnected

    @property
    def buffer_count(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def total_frames(self) -> int:
        """Monotonically increasing count of captured frames."""
        return self._total_frames

    def clear_buffer(self) -> None:
        with self._lock:
            self._buffer.clear()

    def __enter__(self) -> "USBCamera":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()

    # -- Background capture ---------------------------------------------------

    def _save_frame(self, frame: np.ndarray, sync_time: float, seq: int) -> None:
        """Annotate and write a frame to disk (runs in IO thread pool)."""
        label = f"t={sync_time:.2f}s"
        annotated = frame.copy()
        cv2.putText(
            annotated, label,
            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
        )
        path = os.path.join(self._frames_dir, f"frame_{seq:04d}_t{sync_time:.2f}s.jpg")
        cv2.imwrite(path, annotated)

    def _capture_loop(self) -> None:
        interval = 1.0 / self._capture_fps
        fps_window_start = time.monotonic()
        fps_frame_count = 0
        consecutive_failures = 0
        # Declare disconnected after ~1 s of consecutive read failures
        _DISCONNECT_THRESHOLD = max(10, self._capture_fps)

        while self._running:
            t0 = time.monotonic()
            try:
                ret, frame = self._cap.read()
            except Exception:
                ret = False

            try:
                if ret:
                    consecutive_failures = 0
                    with self._lock:
                        self._buffer.append(frame)
                    self._total_frames += 1
                    fps_frame_count += 1
                    if self._save_frames and self._io_pool is not None:
                        self._frame_count += 1
                        sync_time = self._get_time() if self._get_time else 0.0
                        self._io_pool.submit(
                            self._save_frame, frame, sync_time, self._frame_count,
                        )
                else:
                    consecutive_failures += 1
                    if consecutive_failures == _DISCONNECT_THRESHOLD:
                        error("Camera disconnected — USB cable pulled?")
                        self._disconnected = True
                        self._running = False
                        break

                # Log actual FPS every 5 seconds
                fps_elapsed = t0 - fps_window_start
                if fps_elapsed >= 5.0:
                    actual_fps = fps_frame_count / fps_elapsed
                    info(f"Camera FPS: {actual_fps:.1f} (target {self._capture_fps})")
                    fps_window_start = t0
                    fps_frame_count = 0
            except Exception:
                pass  # never let frame processing kill the capture thread

            elapsed = time.monotonic() - t0
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    # -- Frame access ---------------------------------------------------------

    def grab_frame(self) -> np.ndarray | None:
        """Return the most recent frame, or None if buffer is empty."""
        with self._lock:
            return self._buffer[-1].copy() if self._buffer else None

    # -- Preprocessing --------------------------------------------------------

    @staticmethod
    def _preprocess(frame: np.ndarray) -> np.ndarray:
        """Gray-world white balance + Gaussian blur."""
        # Gray-world WB: scale each channel so the average is neutral gray
        avg = frame.mean(axis=(0, 1))
        avg_all = avg.mean()
        scale = avg_all / (avg + 1e-6)
        wb = np.clip(frame * scale, 0, 255).astype(np.uint8)
        # Light Gaussian blur to reduce speckle noise before thresholding
        return cv2.GaussianBlur(wb, (3, 3), 0)

    # -- Per-frame analysis ---------------------------------------------------

    def _analyze_frame(
        self, frame: np.ndarray,
    ) -> dict[str, BlobResult]:
        """Analyze a single frame for all registered colors."""
        pp = self._preprocess(frame)
        hsv = cv2.cvtColor(pp, cv2.COLOR_BGR2HSV)
        # LAB conversion is deferred — only computed if any profile needs it
        lab = None
        results: dict[str, BlobResult] = {}

        for name, profile in self._colors.items():
            if profile.lab_ranges:
                # LAB-based detection with HSV saturation gate
                if lab is None:
                    lab = cv2.cvtColor(pp, cv2.COLOR_BGR2LAB)
                mask = None
                for lower, upper in profile.lab_ranges:
                    m = cv2.inRange(lab, np.array(lower), np.array(upper))
                    mask = m if mask is None else cv2.bitwise_or(mask, m)
                if mask is None:
                    results[name] = BlobResult(present=False)
                    continue
                # Saturation gate: reject low-saturation false positives
                if profile.sat_min > 0:
                    sat_mask = (hsv[:, :, 1] >= profile.sat_min).astype(np.uint8) * 255
                    mask = cv2.bitwise_and(mask, sat_mask)
            else:
                # HSV-based detection
                mask = None
                for lower, upper in profile.hsv_ranges:
                    m = cv2.inRange(hsv, np.array(lower), np.array(upper))
                    mask = m if mask is None else cv2.bitwise_or(mask, m)
                if mask is None:
                    results[name] = BlobResult(present=False)
                    continue

            # Morphological open then close (open removes noise, close fills gaps)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._morph_kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._morph_kernel)

            # Find contours
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
            )

            if not contours:
                results[name] = BlobResult(present=False)
                continue

            # Largest contour by area
            largest = max(contours, key=cv2.contourArea)
            area = int(cv2.contourArea(largest))
            x, y, w, h = cv2.boundingRect(largest)

            if (
                area < profile.min_area
                or w < profile.min_dimension
                or h < profile.min_dimension
            ):
                results[name] = BlobResult(present=False)
                continue

            cx = x + w // 2
            cy = y + h // 2
            results[name] = BlobResult(
                present=True,
                area=area,
                bounding_box=(x, y, w, h),
                center=(cx, cy),
            )

        return results

    # -- Multi-frame consensus ------------------------------------------------

    def analyze(
        self,
        last_n_frames: int | None = None,
        presence_threshold: float | None = None,
    ) -> AnalysisResult:
        """Analyze buffered frames and return consensus results.

        Args:
            last_n_frames: Number of recent frames to analyze (default: all buffered).
            presence_threshold: Fraction of frames a color must appear in
                                to be considered present (default: instance setting).
        """
        if not self._colors:
            warn("No colors registered, nothing to analyze")
            return AnalysisResult(timestamp=time.time())

        threshold = (
            presence_threshold
            if presence_threshold is not None
            else self._presence_threshold
        )

        # Snapshot frames from buffer
        with self._lock:
            frames = list(self._buffer)

        if last_n_frames is not None and last_n_frames < len(frames):
            frames = frames[-last_n_frames:]

        if not frames:
            warn("No frames in buffer to analyze")
            return AnalysisResult(timestamp=time.time())

        # Analyze each frame
        per_frame: list[dict[str, BlobResult]] = [
            self._analyze_frame(f) for f in frames
        ]

        n = len(per_frame)
        consensus: dict[str, ColorConsensus] = {}

        for name in self._colors:
            detections = [
                r[name] for r in per_frame if name in r and r[name].present
            ]
            confidence = len(detections) / n
            present = confidence >= threshold

            if not detections:
                consensus[name] = ColorConsensus(
                    present=False, confidence=confidence,
                )
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
                f"{name}={'present' if c.present else 'absent'}"
                f"({c.confidence:.0%})"
                for name, c in consensus.items()
            ),
        )

        return AnalysisResult(
            colors=consensus,
            frames_analyzed=n,
            timestamp=time.time(),
        )
