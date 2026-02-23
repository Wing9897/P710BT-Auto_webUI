"""Printer service — orchestrates rendering + printing."""
from __future__ import annotations
from ..printer.transport import Transport, USBTransport, BTTransport
from ..printer.protocol import BrotherPrinter
from ..services.label_renderer import LabelSpec, FieldSpec, FieldType, render_label
from ..models.schemas import LabelSpecSchema, PrintRequest
import logging

log = logging.getLogger(__name__)


def _build_label_spec(schema: LabelSpecSchema) -> LabelSpec:
    fields = [
        FieldSpec(
            value=f.value,
            field_type=FieldType(f.field_type),
            font_name=f.font_name,
            font_size=f.font_size,
        )
        for f in schema.fields
    ]
    return LabelSpec(
        fields=fields,
        tape_width_mm=schema.tape_width_mm,
        height_px=schema.height_px,
        margin_px=schema.margin_px,
        spacing_px=schema.spacing_px,
        font_name=schema.font_name,
        font_size=schema.font_size,
    )


def apply_field_mapping(
    template: LabelSpecSchema,
    row: dict[str, str],
    field_mapping: dict[str, str],
) -> LabelSpecSchema:
    """Replace template field values with data from a row using mapping."""
    new_fields = []
    for i, f in enumerate(template.fields):
        col_name = field_mapping.get(str(i))
        value = row.get(col_name, f.value) if col_name else f.value
        new_fields.append(f.model_copy(update={"value": value}))
    return template.model_copy(update={"fields": new_fields})


def _get_transport(req: PrintRequest) -> Transport:
    if req.transport_type == "bluetooth":
        if not req.bt_address:
            raise ValueError("bt_address required for bluetooth transport")
        return BTTransport(req.bt_address, req.bt_channel)
    return USBTransport(req.usb_serial)


def print_labels(req: PrintRequest) -> dict:
    """Print all labels from data rows."""
    transport = _get_transport(req)
    printer = BrotherPrinter(transport)
    printer.connect()

    results = []
    try:
        for i, row in enumerate(req.data):
            label_schema = apply_field_mapping(req.label_template, row, req.field_mapping)
            spec = _build_label_spec(label_schema)
            image = render_label(spec)
            printer.print_image(image, req.margin_px)
            results.append({"index": i, "status": "ok"})
            log.info("Printed label %d/%d", i + 1, len(req.data))
    except Exception as e:
        results.append({"index": len(results), "status": "error", "message": str(e)})
        log.error("Print error at label %d: %s", len(results), e)
    finally:
        printer.close()

    return {
        "total": len(req.data),
        "printed": sum(1 for r in results if r["status"] == "ok"),
        "results": results,
    }
