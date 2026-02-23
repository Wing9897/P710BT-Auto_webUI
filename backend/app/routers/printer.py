"""Printer & label API router."""
from __future__ import annotations
import base64
from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    LabelSpecSchema, PreviewRequest, PrintRequest, PrinterInfo,
    BatchPreviewRequest,
)
from ..services.label_renderer import (
    LabelSpec, FieldSpec, FieldType, render_label_to_bytes, list_available_fonts,
)
from ..services.printer_service import _build_label_spec, apply_field_mapping, print_labels

router = APIRouter(prefix="/api", tags=["printer"])


@router.post("/label/preview")
async def preview_label(req: LabelSpecSchema):
    """Render a single label and return PNG as base64."""
    spec = _build_label_spec(req)
    png_bytes = render_label_to_bytes(spec)
    b64 = base64.b64encode(png_bytes).decode()
    return {"image": f"data:image/png;base64,{b64}"}


@router.post("/label/batch-preview")
async def batch_preview(req: BatchPreviewRequest):
    """Render preview for each data row."""
    previews = []
    for i, row in enumerate(req.data):
        label_schema = apply_field_mapping(req.label_template, row, req.field_mapping)
        spec = _build_label_spec(label_schema)
        png_bytes = render_label_to_bytes(spec)
        b64 = base64.b64encode(png_bytes).decode()
        previews.append({"index": i, "image": f"data:image/png;base64,{b64}"})
    return {"previews": previews}


@router.post("/label/print")
async def print_labels_endpoint(req: PrintRequest):
    """Print labels for all data rows."""
    try:
        result = print_labels(req)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/printer/discover-bt")
async def discover_bt(duration: int = 8):
    """Scan for nearby Bluetooth Classic devices."""
    try:
        from ..printer.transport import discover_bt_devices
        devices = discover_bt_devices(duration=duration)
        return {"devices": devices}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/printer/discover")
async def discover_printers():
    """Discover connected printers (USB)."""
    results = []
    try:
        from ..printer.constants import USBID_BROTHER, SupportedPrinterIDs
        import usb.core
        for pid in SupportedPrinterIDs:
            dev = usb.core.find(idVendor=USBID_BROTHER, idProduct=pid)
            if dev:
                results.append({
                    "type": "usb",
                    "product": dev.product or pid.name,
                    "serial": dev.serial_number,
                    "manufacturer": dev.manufacturer,
                })
    except Exception:
        pass
    return {"printers": results}


@router.get("/printer/status")
async def printer_status(transport_type: str = "usb", serial: str | None = None,
                         bt_address: str | None = None, bt_channel: int = 1):
    """Get printer status."""
    try:
        if transport_type == "bluetooth":
            from ..printer.transport import BTTransport
            tr = BTTransport(bt_address, bt_channel)
        else:
            from ..printer.transport import USBTransport
            tr = USBTransport(serial)
        from ..printer.protocol import BrotherPrinter
        printer = BrotherPrinter(tr)
        printer.connect()
        status = printer.status.to_dict()
        printer.close()
        return status
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/fonts")
async def get_fonts():
    """List available fonts."""
    return {"fonts": list_available_fonts()}
