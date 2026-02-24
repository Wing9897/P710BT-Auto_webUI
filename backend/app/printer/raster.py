"""Raster image preparation for Brother PT printers."""
from PIL import Image
from .constants import MediaWidthToTapeMargin


def make_fit(image: Image.Image, media_width: int) -> Image.Image | None:
    expected_height = MediaWidthToTapeMargin.to_print_width(media_width)
    if image.height == expected_height:
        return image
    if image.width == expected_height:
        return image.transpose(Image.ROTATE_90)
    return None


def has_transparency(img: Image.Image) -> bool:
    if img.info.get("transparency", None) is not None:
        return True
    if img.mode == "P":
        transparent = img.info.get("transparency", -1)
        for _, index in img.getcolors():
            if index == transparent:
                return True
    return False


def select_raster_channel(image: Image.Image) -> Image.Image:
    if image.mode == "P":
        image = image.convert("RGBA") if has_transparency(image) else image.convert("RGB")

    if image.mode == "1":
        return image
    elif image.mode == "L":
        # dark pixel (< 128) = print, white = no print
        return image.point(lambda x: 0xFF if x < 128 else 0)
    elif image.mode == "RGB":
        gray = image.convert("L")
        return gray.point(lambda x: 0xFF if x < 128 else 0)
    elif image.mode == "RGBA":
        # Composite onto white background first, then threshold
        bg = Image.new("RGB", image.size, "white")
        bg.paste(image, mask=image.split()[3])  # use alpha as mask
        gray = bg.convert("L")
        return gray.point(lambda x: 0xFF if x < 128 else 0)
    else:
        raise AttributeError(f"Unsupported color space: {image.mode}")


def compress_buffer(buffer: bytearray) -> bytearray:
    bits = bytearray()
    for i in range(0, len(buffer), 8):
        byte = 0
        for j in range(8):
            if buffer[i + j] > 0:
                byte |= 1 << (7 - j)
        bits.append(byte)
    return bits


def prepare_image(image: Image.Image, media_width: int) -> Image.Image:
    expected = MediaWidthToTapeMargin.to_print_width(media_width)
    result = make_fit(image, media_width)
    if result is None:
        # Auto-resize: scale image so the larger dimension fits expected height
        w, h = image.width, image.height
        # Determine orientation: height should map to tape height
        if h >= w:
            # portrait/square: scale so height = expected
            new_w = max(1, round(w * expected / h))
            resized = image.resize((new_w, expected), Image.LANCZOS)
        else:
            # landscape: scale so width = expected (then rotate)
            new_h = max(1, round(h * expected / w))
            resized = image.resize((expected, new_h), Image.LANCZOS)
        result = make_fit(resized, media_width)
        if result is None:
            # Fallback: force-fit by resizing height directly
            result = image.resize((image.width, expected), Image.LANCZOS)
    return select_raster_channel(result)


def raster_image(prepared_image: Image.Image, media_width: int) -> bytearray:
    buffer = bytearray()
    margin = MediaWidthToTapeMargin.margin[media_width]

    for column in range(prepared_image.width):
        buffer += b"\x00" * margin
        for row in range(prepared_image.height):
            buffer += b"\xFF" if prepared_image.getpixel((column, row)) else b"\x00"
        buffer += b"\x00" * margin

    return compress_buffer(buffer)
