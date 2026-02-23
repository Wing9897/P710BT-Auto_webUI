"""Pydantic schemas for API request/response models."""
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class FieldSpecSchema(BaseModel):
    value: str
    field_type: str = "text"  # text | qr | code128 | code39 | ean13
    font_name: Optional[str] = None
    font_size: Optional[int] = None


class LabelSpecSchema(BaseModel):
    fields: list[FieldSpecSchema]
    tape_width_mm: int = 24
    height_px: Optional[int] = None
    margin_px: int = 8
    spacing_px: int = 6
    font_name: Optional[str] = None
    font_size: Optional[int] = None


class ParseRequest(BaseModel):
    text: Optional[str] = None
    format: str = "auto"      # auto | json | csv | delimited | excel
    delimiter: Optional[str] = None


class PreviewRequest(BaseModel):
    label: LabelSpecSchema
    row_index: int = 0


class BatchPreviewRequest(BaseModel):
    label_template: LabelSpecSchema
    data: list[dict[str, str]]
    field_mapping: dict[str, str] = {}  # field_index -> data column name


class PrintRequest(BaseModel):
    label_template: LabelSpecSchema
    data: list[dict[str, str]]
    field_mapping: dict[str, str] = {}
    transport_type: str = "usb"  # usb | bluetooth
    bt_address: Optional[str] = None
    bt_channel: int = 1
    usb_serial: Optional[str] = None
    margin_px: int = 0


class PrinterInfo(BaseModel):
    media_width_mm: int
    media_type: str
    tape_color: str
    text_color: str


class ParseResponse(BaseModel):
    columns: list[str]
    data: list[dict[str, str]]
    row_count: int
