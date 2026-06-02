"""Drumbot vision daemon.

This process is deployed as a project-owned systemd service by ``raccoon run``.
It owns OpenCV and ``/dev/video0`` so restarting the user robot program does not
tear down the camera device.
"""

from __future__ import annotations

import json
import os
import re
import signal
import threading
import time
from typing import Any

import cv2
from raccoon import error, info, warn, get_transport, shutdown_transport
from raccoon_transport import Transport
from raccoon_transport.types.raccoon.cam_blob_t import cam_blob_t
from raccoon_transport.types.raccoon.cam_detections_t import cam_detections_t
from raccoon_transport.types.raccoon.cam_frame_t import cam_frame_t
from raccoon_transport.types.raccoon.string_t import string_t

from src.hardware.usb_camera import USBCamera
from src.service.color_detection_service import (
    COMMAND_CHANNEL,
    DEFAULT_MIN_AREA,
    DETECTIONS_CHANNEL,
    ERROR_CHANNEL,
    RESPONSE_CHANNEL,
    STATUS_CHANNEL,
)

FRAME_CHANNEL = "raccoon/cam/frame"
DEFAULT_FRAME_TRANSPORT_PROVIDER = "udpm://239.255.76.68:7668?ttl=0"
PRESENCE_THRESHOLD = 0.9
ANALYSIS_FRAMES = 1


class VisionDaemon:
    def __init__(self) -> None:
        self._camera_device = os.environ.get("DRUMBOT_CAMERA_DEVICE", "/dev/video0")
        self._camera_index = _normalize_camera_device(self._camera_device)
        self._camera_codec = os.environ.get("DRUMBOT_CAMERA_CODEC", "YUYV")
        self._stream_fps = int(os.environ.get("DRUMBOT_CAMERA_STREAM_FPS", "10"))
        self._jpeg_quality = int(os.environ.get("DRUMBOT_CAMERA_JPEG_QUALITY", "70"))
        self._transport = get_transport()
        self._frame_transport_provider = os.environ.get(
            "DRUMBOT_CAMERA_FRAME_LCM_PROVIDER",
            DEFAULT_FRAME_TRANSPORT_PROVIDER,
        )
        self._frame_transport = Transport.create(self._frame_transport_provider)
        self._camera = USBCamera(
            camera_index=self._camera_index,
            resolution=(160, 120),
            buffer_size=10,
            capture_fps=30,
            save_frames=False,
            frames_dir="frames",
            get_time=lambda: time.monotonic() - self._start_time,
            codec=self._camera_codec,
        )
        self._camera.add_color(
            "blue",
            hsv_ranges=[],
            lab_ranges=[],
            sat_min=0,
            min_area=DEFAULT_MIN_AREA,
            min_dimension=5,
        )
        self._camera.add_color(
            "pink",
            hsv_ranges=[],
            lab_ranges=[],
            sat_min=0,
            min_area=DEFAULT_MIN_AREA,
            min_dimension=5,
        )

        self._running = False
        self._paused = False
        self._start_time = 0.0
        self._overlay = ""
        self._latest_detections: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_detection_signature: tuple[tuple[str, int, int, int, int], ...] = ()

    def run(self) -> None:
        self._start_time = time.monotonic()
        info(
            "Vision daemon starting "
            f"(device={self._camera_device}, normalized_device={self._camera_index!r}, "
            f"codec={self._camera_codec}, "
            f"stream_fps={self._stream_fps}, jpeg_quality={self._jpeg_quality}, "
            f"frame_transport_provider={self._frame_transport_provider})"
        )
        self._transport.subscribe(COMMAND_CHANNEL, self._on_command, reliable=True)
        self._publish_status(starting=True, started=False)

        attempt = 0
        while True:
            attempt += 1
            try:
                info(f"Opening USB camera (attempt {attempt})")
                self._camera.start(open_retries=60, retry_delay=1.0)
                break
            except Exception as exc:
                self._publish_error(
                    f"Camera open failed: {exc}",
                    phase="open",
                    attempt=attempt,
                    device=self._camera_device,
                )
                self._publish_status(
                    starting=True,
                    started=False,
                    camera_error=str(exc),
                    open_attempt=attempt,
                )
                time.sleep(2.0)

        self._running = True
        info(
            "USB camera opened "
            f"(buffer_count={self._camera.buffer_count}, total_frames={self._camera.total_frames})"
        )
        self._publish_status(starting=False, started=True)

        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        signal.signal(signal.SIGINT, lambda *_: self.stop())

        threading.Thread(target=self._frame_loop, daemon=True).start()
        self._detection_loop()

    def stop(self) -> None:
        info("Stopping vision daemon")
        self._running = False
        self._camera.stop()
        self._frame_transport.close()
        shutdown_transport()
        info("Vision daemon transport shut down")

    def _publish_error(self, message: str, **context: Any) -> None:
        error(message)
        try:
            payload = {
                "timestamp": int(time.time() * 1_000_000),
                "message": message,
                "context": context,
            }
            msg = string_t()
            msg.value = json.dumps(payload)
            self._transport.publish(ERROR_CHANNEL, msg, retained=True)
        except Exception as exc:
            warn(f"Failed to publish vision error on transport: {exc}")

    def _publish_status(self, **extra: Any) -> None:
        msg = string_t()
        payload = {
            "camera_ready": self._camera.is_running,
            "paused": self._paused,
            "total_frames": self._camera.total_frames,
            "buffer_count": self._camera.buffer_count,
        }
        payload.update(extra)
        msg.value = json.dumps(payload)
        self._transport.publish(STATUS_CHANNEL, msg, retained=True)
        info(f"Published vision status: {payload}")

    def _publish_response(self, request_id: str, ok: bool, data: dict[str, Any] | None = None) -> None:
        msg = string_t()
        msg.value = json.dumps(
            {
                "request_id": request_id,
                "ok": ok,
                "data": data or {},
            }
        )
        self._transport.publish(RESPONSE_CHANNEL, msg, reliable=True)

    def _on_command(self, _channel: str, data: bytes) -> None:
        try:
            msg = string_t.decode(data)
            envelope = json.loads(msg.value)
            request_id = envelope.get("request_id", "")
            command = envelope.get("command")
            payload = envelope.get("payload") or {}
        except Exception:
            warn("Ignoring malformed vision command")
            return

        try:
            info(f"Received vision command: command={command!r}, request_id={request_id}, payload={payload}")
            if command == "pause":
                self._paused = True
                self._publish_response(request_id, True)
                info("Vision detection paused")
            elif command == "resume":
                self._paused = False
                self._publish_response(request_id, True)
                info("Vision detection resumed")
            elif command == "reset":
                self._publish_response(request_id, True)
                info("Vision reset acknowledged")
            elif command == "overlay":
                with self._lock:
                    self._overlay = str(payload.get("text") or "")
                self._publish_response(request_id, True)
                info(f"Vision overlay updated: {self._overlay!r}")
            elif command == "apply_calibration":
                self._apply_calibration(int(payload["sat_threshold"]))
                self._publish_response(request_id, True)
            elif command == "capture_calibration_sample":
                max_sat = self._capture_max_saturation()
                self._publish_response(request_id, max_sat is not None, {"max_sat": max_sat})
                info(f"Calibration sample result: max_sat={max_sat}")
            else:
                self._publish_response(request_id, False, {"error": f"unknown command {command!r}"})
        except Exception as exc:
            warn(f"Vision command failed: {exc}")
            self._publish_response(request_id, False, {"error": str(exc)})

    def _apply_calibration(self, sat_threshold: int) -> None:
        info(f"Applying vision calibration: sat_threshold={sat_threshold}")
        self._camera.set_sat_threshold(sat_threshold)
        for color in ("blue", "pink"):
            self._camera.remove_color(color)
            self._camera.add_color(
                color,
                hsv_ranges=[],
                lab_ranges=[],
                sat_min=sat_threshold,
                min_area=DEFAULT_MIN_AREA,
                min_dimension=5,
            )
        self._publish_status(sat_threshold=sat_threshold)

    def _capture_max_saturation(self) -> int | None:
        frame = self._camera.grab_frame()
        if frame is None:
            warn("Calibration sample requested but no frame was available")
            return None
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        return int(hsv[:, :, 1].max())

    def _detection_loop(self) -> None:
        last_frame_id = 0
        log_window_start = time.monotonic()
        detect_count = 0
        last_wait_log = 0.0
        last_no_frame_log = 0.0
        consecutive_detection_failures = 0
        last_detection_error_publish = 0.0
        no_new_frames_since: float | None = None
        last_stall_error_publish = 0.0

        info("Starting detection loop")

        while self._running:
            if self._paused:
                self._publish_empty_detection()
                time.sleep(0.1)
                continue

            current_frame_id = self._camera.total_frames
            if current_frame_id < ANALYSIS_FRAMES or current_frame_id == last_frame_id:
                now = time.monotonic()
                if current_frame_id < ANALYSIS_FRAMES and now - last_wait_log >= 2.0:
                    info(
                        "Detection loop waiting for initial frames "
                        f"(total_frames={current_frame_id}, buffer_count={self._camera.buffer_count})"
                    )
                    last_wait_log = now
                elif current_frame_id == last_frame_id and now - last_no_frame_log >= 2.0:
                    warn(
                        "Detection loop has no new frames "
                        f"(frame_id={current_frame_id}, buffer_count={self._camera.buffer_count})"
                    )
                    last_no_frame_log = now
                if current_frame_id == last_frame_id and current_frame_id > 0:
                    if no_new_frames_since is None:
                        no_new_frames_since = now
                    elif now - no_new_frames_since >= 5.0 and now - last_stall_error_publish >= 5.0:
                        self._publish_error(
                            "Camera stalled — no new frames for >5s",
                            phase="stream",
                            frame_id=current_frame_id,
                            buffer_count=self._camera.buffer_count,
                            stalled_for_seconds=round(now - no_new_frames_since, 2),
                        )
                        last_stall_error_publish = now
                time.sleep(0.005)
                continue
            last_frame_id = current_frame_id
            no_new_frames_since = None

            try:
                result = self._camera.analyze(
                    last_n_frames=ANALYSIS_FRAMES,
                    presence_threshold=PRESENCE_THRESHOLD,
                )
                detections = self._detections_from_result(result)
                with self._lock:
                    self._latest_detections = detections
                self._log_detection_state(detections, current_frame_id)
                self._publish_detections(detections)
                detect_count += 1
                consecutive_detection_failures = 0
            except Exception as exc:
                warn(f"Detection failed: {exc}")
                consecutive_detection_failures += 1
                now = time.monotonic()
                if consecutive_detection_failures >= 5 and now - last_detection_error_publish >= 5.0:
                    self._publish_error(
                        f"Detection failing repeatedly: {exc}",
                        phase="detect",
                        consecutive_failures=consecutive_detection_failures,
                        frame_id=current_frame_id,
                    )
                    last_detection_error_publish = now

            elapsed = time.monotonic() - log_window_start
            if elapsed >= 5.0:
                self._publish_status(
                    detect_fps=detect_count / elapsed,
                    latest_frame_id=current_frame_id,
                    detection_count=len(detections) if 'detections' in locals() else None,
                )
                log_window_start = time.monotonic()
                detect_count = 0

    def _detections_from_result(self, result) -> list[dict[str, Any]]:
        detections: list[dict[str, Any]] = []
        for label in ("blue", "pink"):
            consensus = result.get(label)
            if consensus is None or not consensus.present:
                continue
            x, y, w, h = consensus.median_bbox
            detections.append(
                {
                    "label": label,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "area": consensus.median_area,
                    "confidence": consensus.confidence,
                }
            )
        return detections

    def _publish_empty_detection(self) -> None:
        self._publish_detections([])

    def _publish_detections(self, detections: list[dict[str, Any]]) -> None:
        timestamp = int(time.time() * 1_000_000)
        msg = cam_detections_t()
        msg.timestamp = timestamp
        msg.frame_width = 160
        msg.frame_height = 120
        msg.detections = [_make_blob(d, timestamp) for d in detections]
        msg.num_detections = len(msg.detections)
        self._transport.publish(DETECTIONS_CHANNEL, msg, retained=True)

    def _log_detection_state(self, detections: list[dict[str, Any]], frame_id: int) -> None:
        signature = tuple(
            sorted(
                (det["label"], det["x"], det["y"], det["width"], det["height"])
                for det in detections
            )
        )
        if signature == self._last_detection_signature:
            return

        self._last_detection_signature = signature
        if not detections:
            info(f"Detection state changed: no detections (frame_id={frame_id})")
            return

        summary = ", ".join(
            f"{det['label']}@({det['x']},{det['y']},{det['width']}x{det['height']})"
            f"/conf={det['confidence']:.2f}"
            for det in detections
        )
        info(f"Detection state changed: {summary} (frame_id={frame_id})")

    def _frame_loop(self) -> None:
        interval = 1.0 / max(self._stream_fps, 1)
        last_no_frame_log = 0.0

        info(f"Starting frame publisher loop (fps={self._stream_fps}, jpeg_quality={self._jpeg_quality})")

        while self._running:
            t0 = time.monotonic()
            frame = self._camera.grab_frame()
            if frame is None:
                now = time.monotonic()
                if now - last_no_frame_log >= 2.0:
                    warn(
                        "Frame publisher could not grab a frame "
                        f"(total_frames={self._camera.total_frames}, buffer_count={self._camera.buffer_count})"
                    )
                    last_no_frame_log = now
                time.sleep(0.02)
                continue

            with self._lock:
                overlay = self._overlay
                detections = list(self._latest_detections)

            for det in detections:
                x, y, w, h = det["x"], det["y"], det["width"], det["height"]
                color = (255, 80, 0) if det["label"] == "blue" else (255, 100, 180)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(
                    frame,
                    det["label"],
                    (x, max(12, y - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.38,
                    color,
                    1,
                    cv2.LINE_AA,
                )

            if overlay:
                for color, thickness in [((0, 0, 0), 3), ((255, 255, 255), 1)]:
                    cv2.putText(
                        frame,
                        overlay,
                        (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        thickness,
                        cv2.LINE_AA,
                    )

            ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality])
            if ok:
                h, w = frame.shape[:2]
                msg = cam_frame_t()
                msg.timestamp = int(time.time() * 1_000_000)
                msg.frame_width = w
                msg.frame_height = h
                msg.frame_data = jpeg.tobytes()
                msg.frame_size = len(msg.frame_data)
                msg.detections = [_make_blob(d, msg.timestamp) for d in detections]
                msg.num_detections = len(msg.detections)
                self._frame_transport.publish(FRAME_CHANNEL, msg)
            else:
                warn("JPEG encode failed for current camera frame")

            elapsed = time.monotonic() - t0
            if elapsed < interval:
                time.sleep(interval - elapsed)


def _make_blob(det: dict[str, Any], timestamp: int) -> cam_blob_t:
    blob = cam_blob_t()
    blob.timestamp = timestamp
    blob.label = det["label"]
    blob.x = int(det["x"])
    blob.y = int(det["y"])
    blob.width = int(det["width"])
    blob.height = int(det["height"])
    blob.area = int(det.get("area", 0))
    blob.confidence = float(det.get("confidence", 0.0))
    return blob


def _normalize_camera_device(device: str) -> int | str:
    match = re.fullmatch(r"/dev/video(\d+)", device.strip())
    if match:
        return int(match.group(1))
    return device


def main() -> None:
    attempt = 0
    while True:
        attempt += 1
        daemon = VisionDaemon()
        try:
            daemon.run()
        except Exception as exc:
            error(f"Vision daemon crashed (attempt {attempt}): {exc}")
            try:
                daemon._publish_error(
                    f"Vision daemon crashed and will restart: {exc}",
                    phase="crash",
                    attempt=attempt,
                )
            except Exception as pub_exc:
                warn(f"Could not publish crash error: {pub_exc}")
            try:
                daemon.stop()
            except Exception as stop_exc:
                warn(f"Daemon stop after crash failed: {stop_exc}")
            time.sleep(1.0)
        else:
            info("Vision daemon stopped")
            break


if __name__ == "__main__":
    main()
