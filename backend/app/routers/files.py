"""
文件上传与管理 API
"""
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List

from app.utils.file_manager import file_manager
from app.models.schemas import UploadResponse, FileType
from app.services.supabase_service import supabase_service


router = APIRouter(prefix="/api/v1/files", tags=["files"])


@router.post("/upload", response_model=UploadResponse)
async def upload_files(files: List[UploadFile] = File(...), session_id: str = None):
    """
    上传考勤数据文件
    - 自动识别文件类型（按关键字匹配文件名）
    - 创建处理会话
    """
    if not files:
        raise HTTPException(status_code=400, detail="未上传任何文件")

    # 创建会话
    sid = session_id or file_manager.create_session()

    # 保存所有文件
    saved = []
    for f in files:
        content = await f.read()
        path = file_manager.save_file(sid, f.filename, content)
        saved.append(f.filename)
        # 同时备份到 Supabase Storage（防止 Render 实例睡眠后丢失）
        supabase_service.save_upload_file(sid, f.filename, content)

    # 自动检测文件类型
    matched, missing = file_manager.auto_detect_files(sid)

    # 记录到 Supabase
    supabase_service.create_processing_record(
        session_id=sid,
        date="",
        files_uploaded=saved,
    )

    return UploadResponse(
        session_id=sid,
        files_uploaded=list(matched.keys()),
        missing_files=missing,
        status="uploaded",
    )


@router.get("/{session_id}/files")
async def get_session_files(session_id: str):
    """获取会话已上传文件列表"""
    files = file_manager.get_session_files(session_id)
    matched, missing = file_manager.auto_detect_files(session_id)
    return {
        "session_id": session_id,
        "files": [f.name for f in files],
        "matched": {k: str(v) for k, v in matched.items()},
        "missing": missing,
    }


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话及其所有文件"""
    file_manager.cleanup_session(session_id)
    return {"message": f"会话 {session_id} 已删除"}
