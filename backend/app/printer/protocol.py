"""Brother PT raster protocol commands."""
import packbits
from .constants import (
    LINE_LENGTH_BYTES, MINIMUM_TAPE_POINTS, Mode,
    StatusOffsets, StatusType, STATUS_MESSAGE_LENGTH,
    ErrorInformation1, ErrorInformation2,
    MediaType, TapeColor, TextColor,
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

def set_advanced_mode(chain_print: bool = False) -> bytes:
    value = 0x00 if chain_print else 0x08
    return b"\x1B\x69\x4B" + value.to_bytes(1, "big")

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

def print_without_feeding() -> bytes:
    return b"\x0C"

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
        for _ in range(10):
            self._tr.write(status_information_request())
            raw = self._tr.read(STATUS_MESSAGE_LENGTH)
            if len(raw) >= STATUS_MESSAGE_LENGTH:  # ensure full 32-byte response
                self._status = PrinterStatus(raw)
                return self._status
        raise RuntimeError("Printer did not respond to status request")

    def print_data(self, data: bytes, margin_px: int = 0,
                   last_page: bool = True, chain_print: bool = False):
        if self._status is None:
            raise RuntimeError("Printer status not available; call connect() first")
        mw = self._status.media_width
        self._tr.write(enter_dynamic_command_mode())
        self._tr.write(enable_status_notification())
        self._tr.write(print_information(data, mw))
        self._tr.write(set_mode())
        self._tr.write(set_advanced_mode(chain_print=chain_print))
        self._tr.write(margin_amount(margin_px))
        self._tr.write(set_compression_mode())
        for cmd in gen_raster_commands(data):
            self._tr.write(cmd)
        if last_page:
            self._tr.write(print_with_feeding())
        else:
            self._tr.write(print_without_feeding())

        # wait for completion (max 300 retries ≈ 5 min at USB poll rate)
        for _ in range(300):
            res = self._tr.read()
            if len(res) < STATUS_MESSAGE_LENGTH:
                import time; time.sleep(0.1)  # avoid tight busy-wait
                continue
            st = res[StatusOffsets.STATUS_TYPE]
            if st == StatusType.PRINTING_COMPLETED:
                try:
                    self._tr.read()  # absorb phase change
                except Exception:
                    pass
                return
            elif st == StatusType.ERROR_OCCURRED:
                msgs = []
                e1 = res[StatusOffsets.ERROR_INFORMATION_1]
                e2 = res[StatusOffsets.ERROR_INFORMATION_2]
                if e1 & ErrorInformation1.NO_MEDIA: msgs.append("no media")
                if e1 & ErrorInformation1.CUTTER_JAM: msgs.append("cutter jam")
                if e1 & ErrorInformation1.WEAK_BATTERIES: msgs.append("low batteries")
                if e1 & ErrorInformation1.HIGH_VOLTAGE_ADAPTER: msgs.append("high-voltage adapter")
                if e2 & ErrorInformation2.WRONG_MEDIA: msgs.append("wrong media")
                if e2 & ErrorInformation2.COVER_OPEN: msgs.append("cover open")
                if e2 & ErrorInformation2.OVERHEATING: msgs.append("overheating")
                raise RuntimeError(" | ".join(msgs) if msgs else "Unknown printer error")
            elif st == StatusType.TURNED_OFF:
                raise RuntimeError("Printer turned off during printing")
        raise RuntimeError("Printer did not confirm print completion")

    def print_image(self, image: Image.Image, margin_px: int = 0,
                    last_page: bool = True, chain_print: bool = False):
        self.update_status()
        mw = self._status.media_width
        prepared = prepare_image(image, mw)
        if (prepared.width + margin_px) < MINIMUM_TAPE_POINTS:
            warnings.warn(
                f"Image ({prepared.width}) + margin ({margin_px}) < minimum tape width ({MINIMUM_TAPE_POINTS})"
            )
        data = raster_image(prepared, mw)
        self.print_data(data, margin_px, last_page=last_page, chain_print=chain_print)
