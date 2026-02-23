"""Transport abstraction — USB and Bluetooth backends."""
from abc import ABC, abstractmethod
from typing import Optional
import logging

log = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# USB Transport  (from brother_pt)
# ---------------------------------------------------------------------------

class USBTransport(Transport):
    def __init__(self, serial: Optional[str] = None):
        self._serial = serial
        self._dev = None

    def connect(self) -> None:
        import usb.core
        import usb.util
        from .constants import USBID_BROTHER, SupportedPrinterIDs

        for pid in SupportedPrinterIDs:
            dev = usb.core.find(idVendor=USBID_BROTHER, idProduct=pid)
            if dev is not None:
                if self._serial and dev.serial_number != self._serial:
                    continue
                self._dev = dev
                break

        if self._dev is None:
            raise RuntimeError("No supported USB printer found")

        if self._dev.is_kernel_driver_active(0):
            self._dev.detach_kernel_driver(0)
        self._dev.set_configuration()
        log.info("USB connected: %s", self._dev.product)

    def write(self, data: bytes) -> int:
        from .constants import USB_OUT_EP_ID, USB_TRX_TIMEOUT_MS
        sent = 0
        while sent < len(data):
            sent += self._dev.write(USB_OUT_EP_ID, data[sent:sent + 0x40], USB_TRX_TIMEOUT_MS)
            if sent == 0:
                raise RuntimeError("IO timeout while writing to printer")
        return sent

    def read(self, length: int = 0x80) -> bytes:
        import usb.core
        from .constants import USB_IN_EP_ID, USB_TRX_TIMEOUT_MS
        try:
            return bytes(self._dev.read(USB_IN_EP_ID, length, USB_TRX_TIMEOUT_MS))
        except usb.core.USBError:
            raise RuntimeError("IO timeout while reading from printer")

    def close(self) -> None:
        if self._dev:
            import usb.util
            usb.util.dispose_resources(self._dev)
            self._dev = None


# ---------------------------------------------------------------------------
# Bluetooth RFCOMM Transport
# ---------------------------------------------------------------------------

class BTTransport(Transport):
    """Bluetooth Classic RFCOMM transport using Python built-in socket."""

    def __init__(self, bt_address: str, bt_channel: int = 1):
        self._address = bt_address
        self._channel = bt_channel
        self._sock = None

    def connect(self) -> None:
        import socket
        self._sock = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM,
        )
        self._sock.connect((self._address, self._channel))
        log.info("BT connected: %s ch %d", self._address, self._channel)

    def write(self, data: bytes) -> int:
        return self._sock.send(data)

    def read(self, length: int = 0x80) -> bytes:
        return self._sock.recv(length)

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None


def discover_bt_devices(duration: int = 8) -> list[dict]:
    """Return paired Bluetooth Classic devices from Windows registry.
    
    Reads HKLM\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Devices
    No external libraries required.
    """
    import sys
    if sys.platform != "win32":
        raise RuntimeError("Bluetooth device discovery is only supported on Windows")

    import winreg  # built-in on Windows
    devices = []
    key_path = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
    except FileNotFoundError:
        return []  # No paired devices

    i = 0
    while True:
        try:
            subkey_name = winreg.EnumKey(key, i)
            subkey = winreg.OpenKey(key, subkey_name)
            try:
                raw_name, _ = winreg.QueryValueEx(subkey, "Name")
                if isinstance(raw_name, bytes):
                    name = raw_name.decode("utf-8", errors="ignore").rstrip("\x00")
                else:
                    name = str(raw_name).rstrip("\x00")
                # Registry key name is 12 hex chars = MAC address without colons
                hex_addr = subkey_name.lower().zfill(12)
                address = ":".join(hex_addr[j:j+2] for j in range(0, 12, 2)).upper()
                devices.append({"name": name or "Unknown", "address": address})
            except FileNotFoundError:
                pass
            finally:
                winreg.CloseKey(subkey)
            i += 1
        except OSError:
            break

    winreg.CloseKey(key)
    return devices
