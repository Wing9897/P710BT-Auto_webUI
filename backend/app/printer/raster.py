"""Raster image preparation for Brother PT printers."""
from PIL import Image
from .constants import MediaWidthToTapeMargin, PRINT_HEAD_PINS


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
        return image.point(lambda x: 0xFF if x < 0xFF else 0)
    elif image.mode == "RGB":
        return image.convert("L").point(lambda x: 0xFF if x < 0xFF else 0)
    elif image.mode == "RGBA":
        return image.split()[-1].point(lambda x: 0xFF if x > 0 else 0)
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
    w, h = image.width, image.height
    image = make_fit(image, media_width)
    if image is None:
        expected = MediaWidthToTapeMargin.to_print_width(media_width)
        raise AttributeError(
            f"At least one dimension must match tape width: {expected} vs ({w}, {h})"
        )
    return select_raster_channel(image)


def raster_image(prepared_image: Image.Image, media_width: int) -> bytearray:
    buffer = bytearray()
    margin = MediaWidthToTapeMargin.margin[media_width]

    for column in range(prepared_image.width):
        buffer += b"\x00" * margin
        for row in range(prepared_image.height):
            buffer += b"\xFF" if prepared_image.getpixel((column, row)) else b"\x00"
        buffer += b"\x00" * margin

    return compress_buffer(buffer)
