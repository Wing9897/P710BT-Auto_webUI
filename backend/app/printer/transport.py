"""Transport abstraction — USB backend."""
from abc import ABC, abstractmethod
from typing import Optional
import logging

log = logging.getLogger(__name__)


def _libusb_backend():
    try:
        import libusb_package
        return libusb_package.get_libusb1_backend()
    except ImportError:
        return None


def find_brother_devices():
    """Each supported product id, with the first matching USB device if present."""
    import usb.core
    from .constants import USBID_BROTHER, SupportedPrinterIDs

    backend = _libusb_backend()
    found = []
    for pid in SupportedPrinterIDs:
        dev = usb.core.find(idVendor=USBID_BROTHER, idProduct=pid, backend=backend)
        if dev is not None:
            found.append((pid, dev))
    return found


class Transport(ABC):
    """Abstract byte-level transport to a Brother PT printer."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def write(self, data: bytes) -> int: ...

    @abstractmethod
    def read(self, length: int = 0x80) -> bytes: ...

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()


class USBTransport(Transport):
    def __init__(self, serial: Optional[str] = None):
        self._serial = serial
        self._dev = None

    def connect(self) -> None:
        for _pid, dev in find_brother_devices():
            if self._serial and dev.serial_number != self._serial:
                continue
            self._dev = dev
            break

        if self._dev is None:
            raise RuntimeError("No supported USB printer found")

        # detach_kernel_driver is Linux-only; skip on Windows
        try:
            if self._dev.is_kernel_driver_active(0):
                self._dev.detach_kernel_driver(0)
        except Exception:
            pass
        self._dev.set_configuration()
        log.info("USB connected: %s", self._dev.product)

    def write(self, data: bytes) -> int:
        from .constants import USB_OUT_EP_ID, USB_TRX_TIMEOUT_MS
        sent = 0
        while sent < len(data):
            chunk = self._dev.write(USB_OUT_EP_ID, data[sent:sent + 0x40], USB_TRX_TIMEOUT_MS)
            if chunk == 0:
                raise RuntimeError("IO timeout while writing to printer")
            sent += chunk
        return sent

    def read(self, length: int = 0x80) -> bytes:
        import usb.core
        from .constants import USB_IN_EP_ID, USB_TRX_TIMEOUT_MS
        try:
            return bytes(self._dev.read(USB_IN_EP_ID, length, USB_TRX_TIMEOUT_MS))
        except usb.core.USBError:
            return b""  # timeout → return empty, let caller retry

    def close(self) -> None:
        if self._dev:
            import usb.util
            usb.util.dispose_resources(self._dev)
            self._dev = None
