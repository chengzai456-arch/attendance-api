"""
Pydantic 数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class FileType(str, Enum):
    RAW_DATA = "raw_data"
    LEAVE = "leave"
    ROSTER = "roster"
    SHIFT = "shift"
    RESIGN = "resign"
    GUS_WHITELIST = "gus_whitelist"
    SIGN_THIS_WEEK = "sign_this_week"
    SIGN_LAST_WEEK = "sign_last_week"
    SIGN_BIWEEK = "sign_biweek"


class SessionStatus(str, Enum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStep(str, Enum):
    CLEAN = "clean"
    METRICS = "metrics"
    PIVOT = "pivot"


class UploadResponse(BaseModel):
    session_id: str
    files_uploaded: List[str]
    missing_files: List[str]
    status: SessionStatus


class ProcessRequest(BaseModel):
    session_id: str
    date: Optional[str] = None
    roster_index: Optional[int] = None


class ProcessStatus(BaseModel):
    session_id: str
    status: SessionStatus
    current_step: Optional[ProcessingStep] = None
    progress: float = Field(0.0, ge=0, le=100)
    steps_completed: List[str] = []
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SessionSummary(BaseModel):
    session_id: str
    date: Optional[str] = None
    status: SessionStatus
    total_people: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ExcelFileInfo(BaseModel):
    filename: str
    label: str
    size_bytes: int
    download_url: str


class ProcessResult(BaseModel):
    session_id: str
    summary: Dict[str, Any]
    excel_files: List[ExcelFileInfo] = []
