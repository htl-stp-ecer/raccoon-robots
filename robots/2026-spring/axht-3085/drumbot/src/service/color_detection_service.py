import asyncio
import json
import threading
import time
import uuid
from typing import Any

from raccoon import GenericRobot, RobotService, get_transport

from raccoon_transport.types.raccoon.cam_detections_t import cam_detections_t
from raccoon_transport.types.raccoon.string_t import string_t

DETECTIONS_CHANNEL = "drumbot/cam/detections"
COMMAND_CHANNEL = "drumbot/cam/cmd"
RESPONSE_CHANNEL = "drumbot/cam/response"
STATUS_CHANNEL = "drumbot/cam/status"
ERROR_CHANNEL = "drumbot/cam/error"
DEFAULT_MIN_AREA = 500


class ColorDetectionService(RobotService):
    """Color detection client for the project vision daemon.

    The user program does not import OpenCV or open ``/dev/video0``. Camera
    ownership and image processing live in ``src.daemons.vision``; this service
    only subscribes to semantic detection messages and exposes the old
    lock/reset/detect API used by steps.
    """

    annotate_detections: bool = False

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self._transport = None
        self._subscriptions = []
        self._running = False

        self._lock = threading.Lock()
        self._latest_color: str | None = None
        self._latest_confidence: float = 0.0
        self._color_locked: bool = False
        self._detection_paused: bool = False
        self._color_event = threading.Event()
        self._status_event = threading.Event()
        self._color_first_seen: float | None = None
        self._last_status: dict[str, Any] = {}
        self._pending: dict[str, tuple[threading.Event, dict[str, Any] | None]] = {}

    @property
    def camera(self):
        """Compatibility shim: camera is owned by the daemon now."""
        return None

    def start_camera(self) -> None:
        """Connect to the vision daemon and start receiving detections."""
        if self._running:
            self.info("Vision client already running")
            return

        self._status_event.clear()
        self._last_status = {}
        self._detection_paused = False
        self._transport = get_transport()
        self.info("Connecting to vision daemon transport")
        try:
            self.info("Subscribing to vision status channel")
            status_sub = self._transport.subscribe(STATUS_CHANNEL, self._on_status, request_retained=True)
            self.info("Subscribed to vision status channel")

            self.info("Subscribing to vision response channel")
            response_sub = self._transport.subscribe(RESPONSE_CHANNEL, self._on_response)
            self.info("Subscribed to vision response channel")

            self.info("Subscribing to vision detections channel")
            detections_sub = self._transport.subscribe(DETECTIONS_CHANNEL, self._on_detections)
            self.info("Subscribed to vision detections channel")

            self.info("Subscribing to vision error channel")
            error_sub = self._transport.subscribe(ERROR_CHANNEL, self._on_error, request_retained=True)
            self.info("Subscribed to vision error channel")

            self._subscriptions = [
                status_sub,
                response_sub,
                detections_sub,
                error_sub,
            ]
            self._running = True
            self.info("Vision client subscriptions established")
            self._send_command("resume", {})
            self.info("Waiting for vision daemon ready status")
            deadline = time.monotonic() + 10.0
            while True:
                status = dict(self._last_status)
                if status.get("camera_ready"):
                    self.info(f"Vision daemon ready: {status}")
                    break
                if status and not status.get("starting", False):
                    raise RuntimeError(f"Vision daemon not ready: {status}")

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(
                        f"Vision daemon startup timed out; last_status={status or None}"
                    )

                self.info(
                    "Still waiting for vision daemon status "
                    f"(remaining={remaining:.2f}s, last_status={status or None})"
                )
                self._status_event.clear()
                self._status_event.wait(timeout=remaining)
        except Exception:
            self.stop_camera()
            raise
        self.info("Connected to vision daemon")

    def stop_camera(self) -> None:
        """Disconnect from daemon messages. The daemon keeps the camera open."""
        self._running = False
        if self._transport is not None:
            for sub in self._subscriptions:
                self._transport.unsubscribe(sub)
            self._subscriptions = []
            self._transport = None
        self._status_event.clear()
        self._last_status = {}
        self._pending.clear()
        self.info("Disconnected from vision daemon")

    def _on_error(self, _channel: str, data: bytes) -> None:
        try:
            msg = string_t.decode(data)
            payload = json.loads(msg.value)
        except Exception:
            self.warn("Ignoring malformed vision error message")
            return
        message = payload.get("message", "<unknown>")
        context = payload.get("context") or {}
        phase = context.get("phase") or "unknown"
        cleared = bool(payload.get("cleared", False))
        if cleared:
            # The daemon explicitly cleared an earlier retained error
            # (e.g. camera recovered after open-loop failure). Log at info
            # so a stale "vision is broken" message doesn't sit in the
            # robot's error log forever.
            self.info(f"Vision daemon recovered [{phase}]: {message} (context={context})")
        else:
            self.error(f"Vision daemon error [{phase}]: {message} (context={context})")

    def _on_status(self, _channel: str, data: bytes) -> None:
        try:
            msg = string_t.decode(data)
            self._last_status = json.loads(msg.value)
            self.info(f"Vision status received: {self._last_status}")
            self._status_event.set()
        except Exception:
            self.warn("Ignoring malformed vision status message")

    def _on_response(self, _channel: str, data: bytes) -> None:
        try:
            msg = string_t.decode(data)
            payload = json.loads(msg.value)
            request_id = payload.get("request_id")
        except Exception:
            self.warn("Ignoring malformed vision response message")
            return

        if not request_id:
            return
        pending = self._pending.get(request_id)
        if pending is None:
            return
        event, _ = pending
        self._pending[request_id] = (event, payload)
        event.set()

    def _on_detections(self, _channel: str, data: bytes) -> None:
        try:
            msg = cam_detections_t.decode(data)
        except Exception:
            self.warn("Ignoring malformed vision detection message")
            return

        color: str | None = None
        confidence = 0.0
        if msg.detections:
            best = max(msg.detections, key=lambda blob: blob.confidence)
            if best.label in {"blue", "pink"}:
                color = best.label
                confidence = float(best.confidence)

        if self._detection_paused:
            return

        if color is not None and self._color_first_seen is None:
            self._color_first_seen = time.monotonic()
        elif color is None:
            self._color_first_seen = None

        if color is not None:
            with self._lock:
                self._latest_confidence = confidence
                if not self._color_locked:
                    self._latest_color = color
                    self._color_event.set()

    @property
    def continuous_color_seconds(self) -> float | None:
        first = self._color_first_seen
        if first is None:
            return None
        return time.monotonic() - first

    def pause_detection(self) -> None:
        self._detection_paused = True
        self._send_command("pause", {})

    def resume_detection(self) -> None:
        self._detection_paused = False
        self._send_command("resume", {})

    def detect_single_frame(self) -> str | None:
        return self.peek_color

    def lock_color(self) -> str | None:
        with self._lock:
            self._color_locked = True
            color = self._latest_color
        self.info(f"Color locked: {color}")
        return color

    def reset(self) -> None:
        with self._lock:
            self._latest_color = None
            self._latest_confidence = 0.0
            self._color_locked = False
            self._color_event.clear()
        self._color_first_seen = None
        self._send_command("reset", {})

    async def wait_for_color(self, timeout: float) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._color_event.wait, timeout)

    @property
    def peek_color(self) -> str | None:
        with self._lock:
            return self._latest_color

    @property
    def peek_confidence(self) -> float:
        with self._lock:
            return self._latest_confidence

    async def detect_color(self) -> str | None:
        with self._lock:
            color = self._latest_color
            self._latest_color = None

        if color is None:
            self.error("No color detected by camera - could not determine drum color")
            return None

        self.info(f"Detected color: {color}")
        return color

    def apply_calibration(self, sat_threshold: int) -> None:
        self._send_command("apply_calibration", {"sat_threshold": int(sat_threshold)})
        self.info(f"Color calibration sent: sat_threshold={sat_threshold}")

    def set_overlay(self, text: str) -> None:
        self._send_command("overlay", {"text": text})

    def capture_calibration_sample(self, label: str, timeout: float = 2.0) -> int | None:
        response = self._send_command(
            "capture_calibration_sample",
            {"label": label},
            wait=True,
            timeout=timeout,
        )
        if not response or not response.get("ok"):
            self.warn(f"Calibration capture failed for {label}")
            return None
        data = response.get("data") or {}
        return int(data["max_sat"]) if "max_sat" in data else None

    def _send_command(
        self,
        command: str,
        payload: dict[str, Any],
        *,
        wait: bool = False,
        timeout: float = 1.0,
    ) -> dict[str, Any] | None:
        if self._transport is None:
            return None

        request_id = uuid.uuid4().hex
        event: threading.Event | None = None
        if wait:
            event = threading.Event()
            self._pending[request_id] = (event, None)

        msg = string_t()
        msg.value = json.dumps(
            {
                "request_id": request_id,
                "command": command,
                "payload": payload,
            }
        )
        self.info(f"Sending vision command: command={command!r}, wait={wait}, payload={payload}")
        self._transport.publish(COMMAND_CHANNEL, msg, reliable=wait)

        if not wait or event is None:
            return None
        try:
            if not event.wait(timeout):
                return None
            _, response = self._pending.get(request_id, (event, None))
            return response
        finally:
            self._pending.pop(request_id, None)
