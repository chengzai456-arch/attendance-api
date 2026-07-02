"""
报告查询 API
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

from app.config import SESSIONS_DIR
from app.services.pipeline_runner import PipelineRunner
from app.services.supabase_service import supabase_service


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/{session_id}/html", response_class=HTMLResponse)
async def get_report_html(session_id: str):
    """获取处理后的 HTML 报告（从本地文件读取）"""
    session_dir = SESSIONS_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="会话不存在")

    runner = PipelineRunner(session_id, session_dir)
    html = runner.get_report_html()

    if not html:
        raise HTTPException(status_code=404, detail="报告尚未生成")

    return HTMLResponse(content=html)


@router.get("/{session_id}/json")
async def get_report_json(session_id: str):
    """获取报告 JSON 数据"""
    session_dir = SESSIONS_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="会话不存在")

    runner = PipelineRunner(session_id, session_dir)
    data = runner.get_report_json()

    if not data:
        raise HTTPException(status_code=404, detail="报告数据尚未生成")

    return data


@router.get("/history")
async def get_history(limit: int = 20):
    """获取处理历史列表"""
    records = supabase_service.get_history(limit=limit)
    return {"history": records}


@router.get("/{session_id}/summary")
async def get_report_summary(session_id: str):
    """获取报告摘要"""
    session_dir = SESSIONS_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="会话不存在")

    runner = PipelineRunner(session_id, session_dir)
    return runner.get_summary()
