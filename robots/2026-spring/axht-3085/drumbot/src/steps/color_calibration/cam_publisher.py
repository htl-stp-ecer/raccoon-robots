"""Publish JPEG camera frames to botui's camera viewer via LCM.

Encodes frames in the cam_frame_t binary format that the Dart
CamFrameT decoder expects, including optional detection overlays.
"""

import struct
import threading
import time
from io import BytesIO

import cv2
import numpy as np
from raccoon_transport import Transport

# LCM fingerprints must match the Dart-generated decoders exactly.
CAM_FRAME_FINGERPRINT = 0x4879ec21b38f492b
CAM_BLOB_FINGERPRINT = 0xccbdb8fa6cd129bf

CHANNEL = "libstp/cam/frame"


def _encode_cam_blob(
    label: str,
    x: float,
    y: float,
    width: float,
    height: float,
    area: int,
    confidence: float,
    timestamp: int = 0,
) -> bytes:
    """Encode a single CamBlobT body (no fingerprint prefix)."""
    buf = BytesIO()
    buf.write(struct.pack(">q", timestamp))
    label_bytes = label.encode("utf-8")
    buf.write(struct.pack(">I", len(label_bytes) + 1))
    buf.write(label_bytes)
    buf.write(b"\x00")
    buf.write(struct.pack(">ffff", x, y, width, height))
    buf.write(struct.pack(">i", area))
    buf.write(struct.pack(">f", confidence))
    return buf.getvalue()


def encode_cam_frame(
    jpeg_data: bytes,
    frame_width: int,
    frame_height: int,
    detections: list[dict] | None = None,
) -> bytes:
    """Encode a cam_frame_t message matching the Dart CamFrameT decoder."""
    buf = BytesIO()
    timestamp = int(time.time() * 1_000_000)
    buf.write(struct.pack(">Q", CAM_FRAME_FINGERPRINT))
    buf.write(struct.pack(">q", timestamp))
    buf.write(struct.pack(">iii", frame_width, frame_height, len(jpeg_data)))
    buf.write(jpeg_data)
    dets = detections or []
    buf.write(struct.pack(">i", len(dets)))
    for det in dets:
        buf.write(_encode_cam_blob(
            label=det["label"],
            x=det["x"],
            y=det["y"],
            width=det["width"],
            height=det["height"],
            area=det.get("area", 0),
            confidence=det.get("confidence", 0.0),
            timestamp=timestamp,
        ))
    return buf.getvalue()


class CamPublisher:
    """Background thread that captures frames and publishes them to botui."""

    def __init__(
        self,
        camera_index: int | str = "/dev/video0",
        resolution: tuple[int, int] = (160, 120),
        fps: int = 10,
        jpeg_quality: int = 70,
    ):
        self._camera_index = camera_index
        self._resolution = resolution
        self._fps = fps
        self._jpeg_quality = jpeg_quality

        self._transport = Transport()
        self._cap: cv2.VideoCapture | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._overlay_text: str = ""
        self._detections: list[dict] = []
        self._latest_frame: np.ndarray | None = None
        self._roi_enabled = False

    def start(self) -> None:
        if self._running:
            return
        self._cap = cv2.VideoCapture(self._camera_index, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self._camera_index}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap:
            self._cap.release()
            self._cap = None
        self._transport.close()

    def set_overlay(self, text: str) -> None:
        with self._lock:
            self._overlay_text = text

    def set_detections(self, detections: list[dict]) -> None:
        with self._lock:
            self._detections = list(detections)

    def set_roi_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._roi_enabled = enabled

    def grab_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def _loop(self) -> None:
        interval = 1.0 / self._fps
        while self._running:
            t0 = time.monotonic()
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            with self._lock:
                self._latest_frame = frame.copy()
                overlay = self._overlay_text
                detections = list(self._detections)
                roi_enabled = self._roi_enabled

            h, w = frame.shape[:2]

            # Draw ROI rectangle in center
            if roi_enabled:
                roi_size = min(w, h) // 3
                rx = w // 2 - roi_size // 2
                ry = h // 2 - roi_size // 2
                cv2.rectangle(
                    frame, (rx, ry), (rx + roi_size, ry + roi_size),
                    (0, 255, 0), 2,
                )

            # Overlay text at top
            if overlay:
                cv2.putText(
                    frame, overlay,
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 0, 0), 3, cv2.LINE_AA,
                )
                cv2.putText(
                    frame, overlay,
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 1, cv2.LINE_AA,
                )

            # Encode as JPEG
            _, jpeg = cv2.imencode(
                ".jpg", frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            msg_bytes = encode_cam_frame(
                jpeg.tobytes(), w, h, detections,
            )
            self._transport._lcm.publish(CHANNEL, msg_bytes)

            elapsed = time.monotonic() - t0
            if elapsed < interval:
                time.sleep(interval - elapsed)
