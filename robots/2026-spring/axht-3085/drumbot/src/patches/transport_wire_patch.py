"""Wire-format compatibility patch for cam_blob_t / cam_frame_t /
cam_detections_t.

The lcm-gen'd Python message classes prefix `encode()` with an 8-byte LCM
fingerprint and encode strings as `[len+1][utf8][\\0]`. The Dart hand-written
decoder used by botui and the C++ codec used elsewhere in the stack expect
**no fingerprint** and raw `[len][utf8]` strings, so the LCM-Python format
crashes both with `RangeError` on every frame that contains detections.

Until the codegen is fixed across the stack, every Python process that
publishes or subscribes on the cam_* channels must call `apply()` from this
module so both `encode()` and `decode()` use the cross-language format.
Importing the module already calls `apply()`.
"""

from __future__ import annotations

import struct
from io import BytesIO

from raccoon_transport.types.raccoon.cam_blob_t import cam_blob_t
from raccoon_transport.types.raccoon.cam_detections_t import cam_detections_t
from raccoon_transport.types.raccoon.cam_frame_t import cam_frame_t

_BLOB_TAIL_FMT = ">ffffff"  # x, y, w, h, area, confidence — all float32
_BLOB_TAIL_SIZE = struct.calcsize(_BLOB_TAIL_FMT)


def _blob_encode_one(self: cam_blob_t, buf: BytesIO) -> None:
    buf.write(struct.pack(">q", self.timestamp))
    label_bytes = self.label.encode("utf-8")
    buf.write(struct.pack(">I", len(label_bytes)))
    buf.write(label_bytes)
    buf.write(
        struct.pack(
            _BLOB_TAIL_FMT,
            float(self.x),
            float(self.y),
            float(self.width),
            float(self.height),
            float(self.area),
            float(self.confidence),
        )
    )


def _blob_encode(self: cam_blob_t) -> bytes:
    buf = BytesIO()
    _blob_encode_one(self, buf)
    return buf.getvalue()


def _blob_decode_one(buf: BytesIO) -> cam_blob_t:
    blob = cam_blob_t()
    (blob.timestamp,) = struct.unpack(">q", buf.read(8))
    (label_len,) = struct.unpack(">I", buf.read(4))
    blob.label = buf.read(label_len).decode("utf-8", "replace")
    x, y, w, h, area, conf = struct.unpack(_BLOB_TAIL_FMT, buf.read(_BLOB_TAIL_SIZE))
    blob.x = x
    blob.y = y
    blob.width = w
    blob.height = h
    # Python type stub says `area: int32` but the wire format is float.
    # Round to int for in-process consumers that index by area.
    blob.area = int(area)
    blob.confidence = conf
    return blob


def _blob_decode(data) -> cam_blob_t:
    buf = data if hasattr(data, "read") else BytesIO(data)
    return _blob_decode_one(buf)


def _frame_encode_one(self: cam_frame_t, buf: BytesIO) -> None:
    buf.write(
        struct.pack(
            ">qiii",
            self.timestamp,
            self.frame_width,
            self.frame_height,
            self.frame_size,
        )
    )
    buf.write(bytes(self.frame_data[: self.frame_size]))
    buf.write(struct.pack(">i", self.num_detections))
    for blob in self.detections[: self.num_detections]:
        _blob_encode_one(blob, buf)


def _frame_encode(self: cam_frame_t) -> bytes:
    buf = BytesIO()
    _frame_encode_one(self, buf)
    return buf.getvalue()


def _frame_decode(data) -> cam_frame_t:
    buf = data if hasattr(data, "read") else BytesIO(data)
    msg = cam_frame_t()
    (msg.timestamp, msg.frame_width, msg.frame_height, msg.frame_size) = struct.unpack(
        ">qiii", buf.read(20)
    )
    msg.frame_data = buf.read(msg.frame_size)
    (msg.num_detections,) = struct.unpack(">i", buf.read(4))
    msg.detections = [_blob_decode_one(buf) for _ in range(msg.num_detections)]
    return msg


def _detections_encode(self: cam_detections_t) -> bytes:
    buf = BytesIO()
    buf.write(
        struct.pack(
            ">qii",
            self.timestamp,
            self.frame_width,
            self.frame_height,
        )
    )
    buf.write(struct.pack(">i", self.num_detections))
    for blob in self.detections[: self.num_detections]:
        _blob_encode_one(blob, buf)
    return buf.getvalue()


def _detections_decode(data) -> cam_detections_t:
    buf = data if hasattr(data, "read") else BytesIO(data)
    msg = cam_detections_t()
    (msg.timestamp, msg.frame_width, msg.frame_height) = struct.unpack(
        ">qii", buf.read(16)
    )
    (msg.num_detections,) = struct.unpack(">i", buf.read(4))
    msg.detections = [_blob_decode_one(buf) for _ in range(msg.num_detections)]
    return msg


_applied = False


def apply() -> None:
    global _applied
    if _applied:
        return
    cam_blob_t.encode = _blob_encode
    cam_blob_t._encode_one = _blob_encode_one
    cam_blob_t.decode = staticmethod(_blob_decode)
    cam_frame_t.encode = _frame_encode
    cam_frame_t._encode_one = _frame_encode_one
    cam_frame_t.decode = staticmethod(_frame_decode)
    cam_detections_t.encode = _detections_encode
    cam_detections_t.decode = staticmethod(_detections_decode)
    _applied = True


apply()
