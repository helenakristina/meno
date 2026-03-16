from datetime import date

from pydantic import BaseModel


class ExportRequest(BaseModel):
    date_range_start: date
    date_range_end: date


class ExportResponse(BaseModel):
    signed_url: str
    filename: str
    export_type: str  # 'pdf' or 'csv'
