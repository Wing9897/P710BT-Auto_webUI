"""Label renderer — text/QR/barcode → PIL Image for printing."""
from __future__ import annotations
import io
import textwrap
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import qrcode
import barcode as python_barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

from ..printer.constants import MediaWidthToTapeMargin, TAPE_WIDTHS_MM

# Fallback font
_BUILTIN_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"

# Default: try common system fonts, then fallback to Pillow default
_SYSTEM_FONT_CANDIDATES = [
    "arial.ttf",
    "msyh.ttc",       # Microsoft YaHei (CJK)
    "msjh.ttc",       # Microsoft JhengHei (CJK)
    "NotoSansCJK-Regular.ttc",
    "DejaVuSans.ttf",
]


class FieldType(str, Enum):
    TEXT = "text"
    QR = "qr"
    CODE128 = "code128"
    CODE39 = "code39"
    EAN13 = "ean13"


@dataclass
class FieldSpec:
    value: str
    field_type: FieldType = FieldType.TEXT
    font_name: str | None = None
    font_size: int | None = None  # None = auto


@dataclass
class LabelSpec:
    fields: list[FieldSpec]
    tape_width_mm: int = 24
    height_px: int | None = None   # None = auto from tape
    margin_px: int = 8
    spacing_px: int = 6
    font_name: str | None = None
    font_size: int | None = None   # None = auto


def _resolve_font(name: str | None, size: int) -> ImageFont.FreeTypeFont:
    """Try to load a font by name, falling back to system candidates."""
    candidates = []
    if name:
        candidates.append(name)
        builtin = _BUILTIN_FONTS_DIR / name
        if builtin.exists():
            candidates.insert(0, str(builtin))
    candidates.extend(_SYSTEM_FONT_CANDIDATES)

    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _auto_font_size(text: str, font_name: str | None, max_h: int, max_w: int | None = None) -> int:
    """Binary-search for the largest font size that fits max_h (and optionally max_w)."""
    lo, hi, best = 6, max_h * 2, 10
    for _ in range(20):
        mid = (lo + hi) // 2
        fnt = _resolve_font(font_name, mid)
        bbox = fnt.getbbox(text)
        th = bbox[3] - bbox[1]
        tw = bbox[2] - bbox[0]
        fits = th <= max_h
        if max_w is not None:
            fits = fits and tw <= max_w
        if fits:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text, also breaking on CJK characters."""
    # First try without wrapping
    bbox = font.getbbox(text)
    if (bbox[2] - bbox[0]) <= max_width:
        return [text]

    # Estimate chars per line
    avg_char_w = max((bbox[2] - bbox[0]) / max(len(text), 1), 1)
    chars_per_line = max(int(max_width / avg_char_w), 1)

    lines: list[str] = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width=chars_per_line, break_long_words=True,
                                break_on_hyphens=True)
        lines.extend(wrapped if wrapped else [""])
    return lines


def _render_text_block(
    text: str,
    target_h: int,
    font_name: str | None,
    font_size: int | None,
    max_width: int | None = None,
) -> Image.Image:
    """Render multi-line text to a PIL Image with auto-sizing."""
    if font_size is None:
        font_size = _auto_font_size(text.split("\n")[0] if "\n" in text else text,
                                     font_name, target_h)
    font = _resolve_font(font_name, font_size)

    # wrap
    effective_max_w = max_width or 10000
    lines = _wrap_text(text, font, effective_max_w)

    # re-shrink font if multi-line overflows height
    line_h = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
    total_h = line_h * len(lines) + 2 * (len(lines) - 1)
    while total_h > target_h and font_size > 6:
        font_size -= 1
        font = _resolve_font(font_name, font_size)
        lines = _wrap_text(text, font, effective_max_w)
        line_h = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
        total_h = line_h * len(lines) + 2 * (len(lines) - 1)

    # measure width
    line_widths = []
    for ln in lines:
        bb = font.getbbox(ln)
        line_widths.append(bb[2] - bb[0])
    img_w = max(line_widths) if line_widths else 10

    img = Image.new("RGBA", (img_w, target_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # vertical centering
    y_offset = max((target_h - total_h) // 2, 0)
    for i, ln in enumerate(lines):
        lw = line_widths[i]
        x = (img_w - lw) // 2  # horizontal centering
        draw.text((x, y_offset), ln, fill="black", font=font)
        y_offset += line_h + 2

    return img


def _render_qr(value: str, target_h: int) -> Image.Image:
    qr = qrcode.QRCode(border=1, box_size=max(target_h // 25, 2))
    qr.add_data(value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    img = img.resize((target_h, target_h), Image.NEAREST)
    return img


def _render_barcode(value: str, barcode_type: str, target_h: int) -> Image.Image:
    bc_class = python_barcode.get_barcode_class(barcode_type)
    writer = ImageWriter()
    # render to bytes
    buf = io.BytesIO()
    bc = bc_class(value, writer=writer)
    bc.write(buf, options={"module_height": target_h * 0.6, "quiet_zone": 1, "write_text": False})
    buf.seek(0)
    img = Image.open(buf).convert("RGBA")
    # scale height to target
    ratio = target_h / img.height
    img = img.resize((int(img.width * ratio), target_h), Image.LANCZOS)
    return img


def render_label(spec: LabelSpec) -> Image.Image:
    """Render a full label image from a LabelSpec. Returns RGBA image."""
    tape_h = spec.height_px
    if tape_h is None:
        tape_h = MediaWidthToTapeMargin.to_print_width(spec.tape_width_mm)

    content_h = tape_h - 2 * spec.margin_px
    if content_h < 4:
        content_h = tape_h

    # Render each field
    parts: list[Image.Image] = []
    for f in spec.fields:
        if f.field_type == FieldType.TEXT:
            part = _render_text_block(
                f.value, content_h,
                f.font_name or spec.font_name,
                f.font_size or spec.font_size,
            )
        elif f.field_type == FieldType.QR:
            part = _render_qr(f.value, content_h)
        else:
            part = _render_barcode(f.value, f.field_type.value, content_h)
        parts.append(part)

    if not parts:
        return Image.new("RGBA", (10, tape_h), "white")

    # Compose horizontally with spacing
    total_w = sum(p.width for p in parts) + spec.spacing_px * (len(parts) - 1) + 2 * spec.margin_px
    label = Image.new("RGBA", (total_w, tape_h), "white")

    x = spec.margin_px
    for p in parts:
        y = (tape_h - p.height) // 2
        label.paste(p, (x, y), p)
        x += p.width + spec.spacing_px

    return label


def render_label_to_bytes(spec: LabelSpec, fmt: str = "PNG") -> bytes:
    img = render_label(spec)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def list_available_fonts() -> list[str]:
    """List built-in font files."""
    fonts = []
    if _BUILTIN_FONTS_DIR.exists():
        for f in _BUILTIN_FONTS_DIR.iterdir():
            if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
                fonts.append(f.name)
    # also add system font candidates that are loadable
    for name in _SYSTEM_FONT_CANDIDATES:
        try:
            ImageFont.truetype(name, 12)
            if name not in fonts:
                fonts.append(name)
        except (OSError, IOError):
            pass
    return fonts
