"""Brother PT raster protocol commands."""
import packbits
from .constants import (
    LINE_LENGTH_BYTES, Mode, StatusOffsets, StatusType,
    MediaWidthToTapeMargin, STATUS_MESSAGE_LENGTH,
    ErrorInformation1, ErrorInformation2, MediaType, TapeColor, TextColor,
)
from .transport import Transport
from PIL import Image
from .raster import prepare_image, raster_image
import logging, warnings

log = logging.getLogger(__name__)


# ── Low-level command builders ──────────────────────────────────────────

def invalidate() -> bytes:
    return b"\x00" * 100

def initialize() -> bytes:
    return b"\x1B\x40"

def enter_dynamic_command_mode() -> bytes:
    return b"\x1B\x69\x61\x01"

def enable_status_notification() -> bytes:
    return b"\x1B\x69\x21\x00"

def print_information(data: bytes, media_width_mm: int) -> bytes:
    return (
        b"\x1B\x69\x7A\x84\x00"
        + media_width_mm.to_bytes(1, "little")
        + b"\x00"
        + (len(data) >> 4).to_bytes(4, "little")
        + b"\x00\x00"
    )

def set_mode(mode: Mode = Mode.AUTO_CUT) -> bytes:
    return b"\x1B\x69\x4D" + mode.to_bytes(1, "big")

def set_advanced_mode() -> bytes:
    return b"\x1B\x69\x4B\x08"

def margin_amount(dots: int = 0) -> bytes:
    return b"\x1B\x69\x64" + dots.to_bytes(2, "little")

def set_compression_mode() -> bytes:
    return b"\x4D\x02"

def gen_raster_commands(rasterized_image: bytes) -> list[bytes]:
    raster_cmd = b"\x47"
    zero_cmd = b"\x5A"
    cmds: list[bytes] = []
    for i in range(0, len(rasterized_image), LINE_LENGTH_BYTES):
        line = rasterized_image[i : i + LINE_LENGTH_BYTES]
        if line == b"\x00" * LINE_LENGTH_BYTES:
            cmds.append(zero_cmd)
        else:
            packed = packbits.encode(line)
            cmds.append(raster_cmd + len(packed).to_bytes(2, "little") + packed)
    return cmds

def print_with_feeding() -> bytes:
    return b"\x1A"

def status_information_request() -> bytes:
    return b"\x1B\x69\x53"


# ── High-level printer driver ──────────────────────────────────────────

class PrinterStatus:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.media_width: int = raw[StatusOffsets.MEDIA_WIDTH]
        self.media_type = MediaType(raw[StatusOffsets.MEDIA_TYPE])
        self.tape_color = TapeColor(raw[StatusOffsets.TAPE_COLOR_INFORMATION])
        self.text_color = TextColor(raw[StatusOffsets.TEXT_COLOR_INFORMATION])
        self.status_type = StatusType(raw[StatusOffsets.STATUS_TYPE])

    def to_dict(self) -> dict:
        return {
            "media_width_mm": self.media_width,
            "media_type": self.media_type.name,
            "tape_color": self.tape_color.name,
            "text_color": self.text_color.name,
        }


class BrotherPrinter:
    """Unified printer driver that works over any Transport."""

    def __init__(self, transport: Transport):
        self._tr = transport
        self._status: PrinterStatus | None = None

    @property
    def status(self) -> PrinterStatus | None:
        return self._status

    def connect(self):
        self._tr.connect()
        self.update_status()

    def close(self):
        self._tr.close()

    def update_status(self) -> PrinterStatus:
        self._tr.write(invalidate())
        self._tr.write(initialize())
        raw = b""
        while len(raw) == 0:
            self._tr.write(status_information_request())
            raw = self._tr.read(STATUS_MESSAGE_LENGTH)
        self._status = PrinterStatus(raw)
        return self._status

    def print_data(self, data: bytes, margin_px: int = 0):
        mw = self._status.media_width
        self._tr.write(enter_dynamic_command_mode())
        self._tr.write(enable_status_notification())
        self._tr.write(print_information(data, mw))
        self._tr.write(set_mode())
        self._tr.write(set_advanced_mode())
        self._tr.write(margin_amount(margin_px))
        self._tr.write(set_compression_mode())
        for cmd in gen_raster_commands(data):
            self._tr.write(cmd)
        self._tr.write(print_with_feeding())

        # wait for completion
        while True:
            res = self._tr.read()
            if len(res) > 0:
                st = res[StatusOffsets.STATUS_TYPE]
                if st == StatusType.PRINTING_COMPLETED:
                    try:
                        self._tr.read()  # absorb phase change
                    except Exception:
                        pass
                    return
                elif st == StatusType.ERROR_OCCURRED:
                    msgs = []
                    if res[8] & 0x01: msgs.append("no media")
                    if res[8] & 0x04: msgs.append("cutter jam")
                    if res[8] & 0x08: msgs.append("low batteries")
                    if res[8] & 0x40: msgs.append("high-voltage adapter")
                    if res[9] & 0x01: msgs.append("wrong media")
                    if res[9] & 0x10: msgs.append("cover open")
                    if res[9] & 0x20: msgs.append("overheating")
                    raise RuntimeError(" | ".join(msgs) if msgs else "Unknown printer error")

    def print_image(self, image: Image.Image, margin_px: int = 0):
        self.update_status()
        mw = self._status.media_width
        prepared = prepare_image(image, mw)
        from .constants import MINIMUM_TAPE_POINTS
        if (prepared.width + margin_px) < MINIMUM_TAPE_POINTS:
            warnings.warn(
                f"Image ({prepared.width}) + margin ({margin_px}) < minimum tape width ({MINIMUM_TAPE_POINTS})"
            )
        data = raster_image(prepared, mw)
        self.print_data(data, margin_px)
