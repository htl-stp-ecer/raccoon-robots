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
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import cv2
import numpy as np
from raccoon import error, info, warn, get_transport, shutdown_transport
from raccoon_transport.channels import Channels as TransportChannels
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
    FRAME_CHANNEL,
    RESPONSE_CHANNEL,
    STATUS_CHANNEL,
)


# Bring encode/decode of cam_blob_t, cam_frame_t, cam_detections_t in line
# with the C++/Dart wire format (no LCM fingerprint, raw-length strings).
# See src/transport_wire_patch.py for details.
import src.patches.transport_wire_patch  # noqa: F401

PRESENCE_THRESHOLD = 0.9
ANALYSIS_FRAMES = 1


class VisionDaemon:
    def __init__(self) -> None:
        self._camera_device = os.environ.get("DRUMBOT_CAMERA_DEVICE", "/dev/video0")
        self._camera_index = _normalize_camera_device(self._camera_device)
        self._camera_codec = os.environ.get("DRUMBOT_CAMERA_CODEC", "YUYV")
        self._stream_fps = int(os.environ.get("DRUMBOT_CAMERA_STREAM_FPS", "15"))
        self._jpeg_quality = int(os.environ.get("DRUMBOT_CAMERA_JPEG_QUALITY", "60"))
        self._transport = get_transport()
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
        self._camera.add_color("blue", min_area=DEFAULT_MIN_AREA, min_dimension=5)
        self._camera.add_color("pink", min_area=DEFAULT_MIN_AREA, min_dimension=5)

        # Directory that holds raw calibration sample frames. A new sub-
        # directory per ``start_time`` keeps re-runs from clobbering each
        # other and gives us something to load offline next session.
        self._calibration_samples_root = os.environ.get(
            "DRUMBOT_CALIBRATION_SAMPLES_DIR", "calibration_samples"
        )
        self._calibration_session_dir: str | None = None
        self._calibration_sample_count = int(os.environ.get("DRUMBOT_CALIBRATION_SAMPLE_COUNT", "30"))
        self._calibration_settle_seconds = float(os.environ.get("DRUMBOT_CALIBRATION_SETTLE_SECONDS", "0.25"))
        # Off by default: capturing detection debug frames is heavy SD-card
        # I/O. Only enable it when DRUMBOT_DETECTION_DEBUG is explicitly set to
        # a truthy value ("1"/"true"/"yes"/"on").
        self._detection_debug_enabled = os.environ.get(
            "DRUMBOT_DETECTION_DEBUG", "0"
        ).strip().lower() in ("1", "true", "yes", "on")
        self._detection_debug_root = os.environ.get("DRUMBOT_DETECTION_DEBUG_DIR", "detection_debug")
        self._detection_debug_dir: str | None = None
        self._detection_debug_seq = 0
        self._detection_debug_io = ThreadPoolExecutor(max_workers=1) if self._detection_debug_enabled else None

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
            f"analysis_frames={ANALYSIS_FRAMES}, detection_debug={self._detection_debug_enabled})"
        )
        self._transport.subscribe(COMMAND_CHANNEL, self._on_command, reliable=True)
        self._publish_status(starting=True, started=False)

        attempt = 0
        open_had_failed = False
        while True:
            attempt += 1
            try:
                info(f"Opening USB camera (attempt {attempt})")
                self._camera.start(open_retries=60, retry_delay=1.0)
                break
            except Exception as exc:
                open_had_failed = True
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
        # If we ever published an error during the open loop, broadcast a
        # cleared-event so subscribers (Robot UI, color_detection_service,
        # tests) replace the retained error snapshot with "recovered" instead
        # of seeing a stale "Camera open failed" forever.
        if open_had_failed:
            self._publish_recovered(
                "Camera open recovered",
                phase="open",
                attempts=attempt,
                device=self._camera_device,
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
        if self._detection_debug_io is not None:
            self._detection_debug_io.shutdown(wait=True)
            self._detection_debug_io = None
        shutdown_transport()
        info("Vision daemon transport shut down")

    def _publish_error(self, message: str, **context: Any) -> None:
        error(message)
        self._publish_vision_event(message, cleared=False, **context)

    def _publish_recovered(self, message: str, **context: Any) -> None:
        info(f"Vision recovered: {message}")
        self._publish_vision_event(message, cleared=True, **context)

    def _publish_vision_event(self, message: str, *, cleared: bool, **context: Any) -> None:
        """Publish to both the project-specific raccoon/cam/error channel
        and the official raccoon/errors string channel. Both are retained
        so a late subscriber sees the latest state (error OR recovery).
        cleared=True signals subscribers that the prior retained error is
        resolved — they should drop any "vision is broken" UI state.
        """
        phase = context.get("phase", "unknown")
        prefix = "Vision RECOVERED" if cleared else "Vision ERROR"
        official_text = f"{prefix} [{phase}]: {message}"
        if context:
            official_text += f" (context={context})"

        try:
            payload = {
                "timestamp": int(time.time() * 1_000_000),
                "message": message,
                "cleared": cleared,
                "context": context,
            }
            msg = string_t()
            msg.value = json.dumps(payload)
            self._transport.publish(ERROR_CHANNEL, msg, retained=True)
        except Exception as exc:
            warn(f"Failed to publish vision event on project error channel: {exc}")

        try:
            official_msg = string_t()
            official_msg.value = official_text
            self._transport.publish(TransportChannels.ERROR_MESSAGES, official_msg, retained=True)
        except Exception as exc:
            warn(f"Failed to publish vision event on raccoon/errors: {exc}")

    def _publish_status(self, **extra: Any) -> None:
        msg = string_t()
        payload = {
            "camera_ready": self._camera.is_running,
            "paused": self._paused,
            "total_frames": self._camera.total_frames,
            "buffer_count": self._camera.buffer_count,
            "chroma_threshold": self._camera.chroma_threshold,
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
                threshold = int(payload.get("chroma_threshold", payload.get("sat_threshold", 0)))
                self._apply_calibration(threshold)
                self._publish_response(request_id, True)
            elif command == "capture_calibration_sample":
                label = str(payload.get("label", "sample"))
                result = self._capture_calibration_samples(label)
                self._publish_response(request_id, result is not None, result or {})
                info(f"Calibration sample result: label={label}, summary={result}")
            else:
                self._publish_response(request_id, False, {"error": f"unknown command {command!r}"})
        except Exception as exc:
            warn(f"Vision command failed: {exc}")
            self._publish_response(request_id, False, {"error": str(exc)})

    def _apply_calibration(self, chroma_threshold: int) -> None:
        info(f"Applying vision calibration: chroma_threshold={chroma_threshold}")
        self._camera.set_chroma_threshold(chroma_threshold)
        self._publish_status(chroma_threshold=chroma_threshold)

    def _ensure_calibration_session_dir(self) -> str:
        if self._calibration_session_dir is None:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            self._calibration_session_dir = os.path.join(self._calibration_samples_root, stamp)
            os.makedirs(self._calibration_session_dir, exist_ok=True)
            info(f"Calibration samples will be written to {self._calibration_session_dir}")
        return self._calibration_session_dir

    def _capture_calibration_samples(self, label: str) -> dict[str, Any] | None:
        """Capture N raw frames, persist them, and return chroma stats.

        Frames are written as lossless PNG so a future offline session can
        load them and re-run the detector without touching the camera.
        """
        session_dir = self._ensure_calibration_session_dir()
        safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", label) or "sample"
        out_dir = os.path.join(session_dir, safe_label)
        os.makedirs(out_dir, exist_ok=True)

        n = max(1, self._calibration_sample_count)
        captured: list[np.ndarray] = []
        seen_ids: set[int] = set()
        start_frame_id = self._camera.total_frames
        self._camera.clear_buffer()
        if self._calibration_settle_seconds > 0:
            time.sleep(self._calibration_settle_seconds)

        deadline = time.monotonic() + 3.0
        while len(captured) < n and time.monotonic() < deadline:
            frame_id = self._camera.total_frames
            if frame_id > start_frame_id and frame_id not in seen_ids:
                frame = self._camera.grab_frame()
                if frame is not None:
                    captured.append(frame)
                    seen_ids.add(frame_id)
                    continue
            time.sleep(0.01)

        if not captured:
            warn(f"Calibration sample requested but no frames were available (label={label})")
            return None

        stats_per_frame: list[dict[str, float]] = []
        for idx, frame in enumerate(captured):
            path = os.path.join(out_dir, f"frame_{idx:03d}.png")
            try:
                cv2.imwrite(path, frame)
            except Exception as exc:
                warn(f"Failed to write calibration frame {path}: {exc}")
            stats_per_frame.append(self._camera.chroma_stats(frame))

        def _avg(key: str) -> float:
            vals = [s[key] for s in stats_per_frame]
            return float(sum(vals) / len(vals))

        summary = {
            "label": safe_label,
            "frames_captured": len(captured),
            "samples_dir": os.path.abspath(out_dir),
            "median_chroma": _avg("median_chroma"),
            "p95_chroma": _avg("p95_chroma"),
            "max_chroma": max(s["max_chroma"] for s in stats_per_frame),
            "mean_a_chromatic": _avg("mean_a_chromatic"),
            "mean_b_chromatic": _avg("mean_b_chromatic"),
            "chromatic_fraction": _avg("chromatic_fraction"),
        }
        info(
            "Calibration capture: "
            f"label={safe_label}, frames={len(captured)}, "
            f"start_frame_id={start_frame_id}, settle_s={self._calibration_settle_seconds:.2f}, "
            f"median_C={summary['median_chroma']:.1f}, p95_C={summary['p95_chroma']:.1f}, "
            f"max_C={summary['max_chroma']:.1f}, "
            f"mean_a*={summary['mean_a_chromatic']:.1f}, mean_b*={summary['mean_b_chromatic']:.1f}, "
            f"chromatic_frac={summary['chromatic_fraction']:.2f}, dir={out_dir}"
        )
        return summary

    def _detection_loop(self) -> None:
        last_frame_id = 0
        log_window_start = time.monotonic()
        detect_count = 0
        last_wait_log = 0.0
        last_no_frame_log = 0.0
        consecutive_detection_failures = 0
        last_detection_error_publish = 0.0
        detect_error_active = False
        no_new_frames_since: float | None = None
        last_stall_error_publish = 0.0
        stall_error_active = False

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
                        stall_error_active = True
                time.sleep(0.005)
                continue
            last_frame_id = current_frame_id
            no_new_frames_since = None
            if stall_error_active:
                self._publish_recovered(
                    "Camera stream recovered — new frames flowing again",
                    phase="stream",
                    frame_id=current_frame_id,
                )
                stall_error_active = False

            try:
                result = self._camera.analyze(
                    last_n_frames=ANALYSIS_FRAMES,
                    presence_threshold=PRESENCE_THRESHOLD,
                )
                detections = self._detections_from_result(result)
                with self._lock:
                    self._latest_detections = detections
                self._log_detection_state(detections, current_frame_id)
                self._save_detection_debug_frames(detections, current_frame_id)
                self._publish_detections(detections)
                detect_count += 1
                consecutive_detection_failures = 0
                if detect_error_active:
                    self._publish_recovered(
                        "Detection pipeline recovered",
                        phase="detect",
                        frame_id=current_frame_id,
                    )
                    detect_error_active = False
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
                    detect_error_active = True

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

    def _ensure_detection_debug_dir(self) -> str:
        if self._detection_debug_dir is None:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            self._detection_debug_dir = os.path.join(self._detection_debug_root, stamp)
            os.makedirs(self._detection_debug_dir, exist_ok=True)
            warn(
                "Detection debug capture is ENABLED — writing raw+annotated PNGs "
                f"and JSON to {self._detection_debug_dir}. This is heavy SD-card "
                "I/O and can fill the disk; unset DRUMBOT_DETECTION_DEBUG to stop."
            )
        return self._detection_debug_dir

    def _save_detection_debug_frames(self, detections: list[dict[str, Any]], frame_id: int) -> None:
        if not self._detection_debug_enabled or not detections:
            return

        frames = self._camera.grab_frames(ANALYSIS_FRAMES)
        if not frames:
            warn(f"Could not save detection debug frames: no frames available (frame_id={frame_id})")
            return

        out_dir = self._ensure_detection_debug_dir()
        labels = "-".join(sorted({str(det["label"]) for det in detections}))
        self._detection_debug_seq += 1
        if self._detection_debug_seq % 50 == 0:
            warn(
                f"Detection debug still writing: {self._detection_debug_seq} frame "
                f"sets saved to {out_dir} (SD-card filling up)."
            )
        prefix = f"{self._detection_debug_seq:05d}_frame{frame_id}_{labels}"
        metadata = {
            "frame_id": frame_id,
            "analysis_frames": ANALYSIS_FRAMES,
            "detections": detections,
        }

        if self._detection_debug_io is None:
            return

        self._detection_debug_io.submit(
            self._write_detection_debug_frames,
            out_dir,
            prefix,
            frames,
            metadata,
        )

    def _write_detection_debug_frames(
        self,
        out_dir: str,
        prefix: str,
        frames: list[np.ndarray],
        metadata: dict[str, Any],
    ) -> None:
        try:
            for idx, frame in enumerate(frames):
                raw_path = os.path.join(out_dir, f"{prefix}_raw_{idx:02d}.png")
                debug_path = os.path.join(out_dir, f"{prefix}_debug_{idx:02d}.png")
                cv2.imwrite(raw_path, frame)
                cv2.imwrite(debug_path, self._camera.get_annotated_debug_frame(frame))

            metadata_path = os.path.join(out_dir, f"{prefix}.json")
            with open(metadata_path, "w", encoding="utf-8") as fh:
                json.dump(metadata, fh, indent=2, sort_keys=True)
        except Exception as exc:
            warn(f"Failed to save detection debug frames: {exc}")

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
        publish_window_start = time.monotonic()
        publish_count = 0
        bytes_window = 0

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
                # Detections embedded inside cam_frame_t hit an
                # encoder/decoder mismatch between the Python
                # lcm-generated cam_blob_t (string written as
                # length+1 with trailing NUL) and the hand-written
                # Dart decoder used by botui. Any frame with
                # num_detections > 0 crashes CamFrameT.decodeBody with
                # a RangeError, so botui never sees a frame and the
                # UI stays stuck at "Waiting for camera…".
                # Fix: drop the embedded detections. The UI subscribes
                # to the dedicated raccoon/cam/detections channel
                # anyway and draws boxes from there.
                msg.detections = []
                msg.num_detections = 0
                self._transport.publish(FRAME_CHANNEL, msg)
                publish_count += 1
                bytes_window += msg.frame_size
            else:
                warn("JPEG encode failed for current camera frame")

            now = time.monotonic()
            window = now - publish_window_start
            if window >= 2.0:
                info(
                    "Frame publisher: "
                    f"publish_fps={publish_count / window:.1f}, "
                    f"avg_kb={bytes_window / max(publish_count, 1) / 1024:.1f}, "
                    f"window_s={window:.1f}"
                )
                publish_window_start = now
                publish_count = 0
                bytes_window = 0

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
