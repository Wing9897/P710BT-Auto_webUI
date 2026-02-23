"""Data import API router."""
from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional

from ..models.schemas import ParseRequest, ParseResponse
from ..services.data_parser import parse_auto

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/parse", response_model=ParseResponse)
async def parse_data(
    text: Optional[str] = Form(None),
    format: str = Form("auto"),
    delimiter: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Parse input data from text or file upload."""
    file_bytes = None
    if file is not None:
        file_bytes = await file.read()
        if file.filename and file.filename.endswith((".xlsx", ".xls")):
            format = "excel"
        elif text is None:
            text = file_bytes.decode("utf-8", errors="replace")

    rows = parse_auto(text=text, file_bytes=file_bytes, format=format, delimiter=delimiter)

    columns = list(rows[0].keys()) if rows else []
    return ParseResponse(columns=columns, data=rows, row_count=len(rows))
