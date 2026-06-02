"""Background thread that publishes frames from a shared USBCamera to botui."""

import os
import threading
import time

import cv2
import numpy as np
from raccoon_transport import Transport
from raccoon_transport.types.raccoon.cam_blob_t import cam_blob_t
from raccoon_transport.types.raccoon.cam_frame_t import cam_frame_t

from src.hardware.usb_camera import USBCamera

CHANNEL = "raccoon/cam/frame"
DEFAULT_FRAME_TRANSPORT_PROVIDER = "udpm://239.255.76.68:7668?ttl=0"


class CamPublisher:
    """Publishes frames from an already-running USBCamera to the UI channel.

    Does not own the camera — the camera is started once in the setup mission
    and stays open for the entire run. This publisher just samples its latest
    frame at a configurable FPS and pushes it to ``raccoon/cam/frame``.
    """

    def __init__(
        self,
        camera: USBCamera,
        fps: int = 10,
        jpeg_quality: int = 70,
    ):
        self._camera = camera
        self._fps = fps
        self._jpeg_quality = jpeg_quality

        self._frame_transport_provider = os.environ.get(
            "DRUMBOT_CAMERA_FRAME_LCM_PROVIDER",
            DEFAULT_FRAME_TRANSPORT_PROVIDER,
        )
        self._frame_transport = Transport.create(self._frame_transport_provider)
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
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._frame_transport.close()

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
            frame = self._camera.grab_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            with self._lock:
                self._latest_frame = frame.copy()
                overlay = self._overlay_text
                detections = list(self._detections)
                roi_enabled = self._roi_enabled

            h, w = frame.shape[:2]

            if roi_enabled:
                roi_size = min(w, h) // 3
                rx, ry = w // 2 - roi_size // 2, h // 2 - roi_size // 2
                cv2.rectangle(frame, (rx, ry), (rx + roi_size, ry + roi_size), (0, 255, 0), 2)

            if overlay:
                for color, thickness in [((0, 0, 0), 3), ((255, 255, 255), 1)]:
                    cv2.putText(frame, overlay, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, thickness, cv2.LINE_AA)

            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality])
            jpeg_bytes = jpeg.tobytes()

            timestamp = int(time.time() * 1_000_000)
            msg = cam_frame_t()
            msg.timestamp = timestamp
            msg.frame_width = w
            msg.frame_height = h
            msg.frame_data = jpeg_bytes
            msg.frame_size = len(jpeg_bytes)
            msg.detections = [_make_blob(d, timestamp) for d in detections]
            msg.num_detections = len(msg.detections)

            self._frame_transport.publish(CHANNEL, msg)

            elapsed = time.monotonic() - t0
            if elapsed < interval:
                time.sleep(interval - elapsed)


def _make_blob(det: dict, timestamp: int) -> cam_blob_t:
    blob = cam_blob_t()
    blob.timestamp = timestamp
    blob.label = det["label"]
    blob.x = det["x"]
    blob.y = det["y"]
    blob.width = det["width"]
    blob.height = det["height"]
    blob.area = det.get("area", 0)
    blob.confidence = det.get("confidence", 0.0)
    return blob
