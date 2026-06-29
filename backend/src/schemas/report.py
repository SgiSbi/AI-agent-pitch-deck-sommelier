from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReportCreate(BaseModel):
    presentation_dir: str
    user_id: Optional[int] = None
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    report_log_path: Optional[str] = None


class ReportRead(BaseModel):
    id: int
    presentation_dir: str
    user_id: Optional[int] = None
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    report_log_path: Optional[str] = None
    status: str = "processing"
    error_message: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    tavily_requests: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}
