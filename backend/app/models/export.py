from datetime import date

from pydantic import BaseModel


class ExportRequest(BaseModel):
    date_range_start: date
    date_range_end: date
