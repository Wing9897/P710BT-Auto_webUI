"""Brother PT printer constants — enums and protocol values."""
from enum import IntEnum, IntFlag

PRINT_HEAD_PINS = 128
PRINT_DPI = 180
USBID_BROTHER = 0x04F9
LINE_LENGTH_BYTES = 0x10
MINIMUM_TAPE_POINTS = 174  # 25.4 mm @ 180dpi
USB_OUT_EP_ID = 0x02
USB_IN_EP_ID = 0x81
USB_TRX_TIMEOUT_MS = 15000
STATUS_MESSAGE_LENGTH = 32


class SupportedPrinterIDs(IntEnum):
    E550W = 0x2060
    P750W = 0x2062
    P710BT = 0x20AF


class StatusOffsets(IntEnum):
    ERROR_INFORMATION_1 = 8
    ERROR_INFORMATION_2 = 9
    MEDIA_WIDTH = 10
    MEDIA_TYPE = 11
    MODE = 15
    MEDIA_LENGTH = 17
    STATUS_TYPE = 18
    PHASE_TYPE = 19
    PHASE_NUMBER = 20
    NOTIFICATION_NUMBER = 22
    TAPE_COLOR_INFORMATION = 24
    TEXT_COLOR_INFORMATION = 25
    HARDWARE_SETTINGS = 26


class MediaWidthToTapeMargin:
    margin = {
        4: 52,   # 3.5mm
        6: 48,   # 6mm
        9: 39,   # 9mm
        12: 29,  # 12mm
        18: 8,   # 18mm
        24: 0,   # 24mm
    }

    @staticmethod
    def to_print_width(tape_width: int) -> int:
        return PRINT_HEAD_PINS - MediaWidthToTapeMargin.margin[tape_width] * 2


class ErrorInformation1(IntFlag):
    NO_MEDIA = 0x01
    CUTTER_JAM = 0x04
    WEAK_BATTERIES = 0x08
    HIGH_VOLTAGE_ADAPTER = 0x40


class ErrorInformation2(IntFlag):
    WRONG_MEDIA = 0x01
    COVER_OPEN = 0x10
    OVERHEATING = 0x20


class MediaType(IntEnum):
    NO_MEDIA = 0x00
    LAMINATED_TAPE = 0x01
    NON_LAMINATED_TAPE = 0x03
    HEAT_SHRINK_TUBE = 0x11
    INCOMPATIBLE_TAPE = 0xFF


class Mode(IntFlag):
    AUTO_CUT = 0x40
    MIRROR_PRINTING = 0x80


class StatusType(IntEnum):
    REPLY_TO_STATUS_REQUEST = 0x00
    PRINTING_COMPLETED = 0x01
    ERROR_OCCURRED = 0x02
    TURNED_OFF = 0x04
    NOTIFICATION = 0x05
    PHASE_CHANGE = 0x06


class TapeColor(IntEnum):
    WHITE = 0x01
    OTHER = 0x02
    CLEAR = 0x03
    RED = 0x04
    BLUE = 0x05
    YELLOW = 0x06
    GREEN = 0x07
    BLACK = 0x08
    CLEAR_WHITE_TEXT = 0x09
    MATTE_WHITE = 0x20
    MATTE_CLEAR = 0x21
    MATTE_SILVER = 0x22
    SATIN_GOLD = 0x23
    SATIN_SILVER = 0x24
    BLUE_D = 0x30
    RED_D = 0x31
    FLUORESCENT_ORANGE = 0x40
    FLUORESCENT_YELLOW = 0x41
    BERRY_PINK_S = 0x50
    LIGHT_GRAY_S = 0x51
    LIME_GREEN_S = 0x52
    YELLOW_F = 0x60
    PINK_F = 0x61
    BLUE_F = 0x62
    WHITE_HEAT_SHRINK_TUBE = 0x70
    WHITE_FLEX_ID = 0x90
    YELLOW_FLEX_ID = 0x91
    CLEANING = 0xF0
    STENCIL = 0xF1
    INCOMPATIBLE = 0xFF


class TextColor(IntEnum):
    WHITE = 0x01
    OTHER = 0x02
    RED = 0x04
    BLUE = 0x05
    BLACK = 0x08
    GOLD = 0x0A
    BLUE_F = 0x62
    CLEANING = 0xF0
    STENCIL = 0xF1
    INCOMPATIBLE = 0xFF


# Tape width options for UI
TAPE_WIDTHS_MM = [4, 6, 9, 12, 18, 24]
