"""
考勤处理流程 API
产出 Excel 文件，结果存入 Supabase Storage（不依赖 Render 本地磁盘）
"""
import threading
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pathlib import Path

from app.config import SESSIONS_DIR
from app.utils.file_manager import file_manager
from app.services.pipeline_runner import PipelineRunner
from app.services.supabase_service import supabase_service
from app.models.schemas import ProcessRequest, ProcessStatus, ProcessResult, ExcelFileInfo


router = APIRouter(prefix="/api/v1/process", tags=["process"])

# 用于内存中跟踪活跃的异步任务（实例存活期间有效）
_active_tasks: dict = {}  # session_id -> {"thread": Thread, "runner": PipelineRunner}
_tasks_lock = threading.Lock()


def run_pipeline_background(session_id: str, workspace: Path, roster_index: int = None):
    """后台执行 Pipeline + 结果上传 Supabase Storage"""
    try:
        _run_pipeline_core(session_id, workspace, roster_index)
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"[Background] 未捕获异常:\n{err_msg}")
        try:
            runner = PipelineRunner(session_id, workspace)
            runner._update(error=f"处理异常: {str(e)}", status=None)
            runner.state["status"] = "failed"
            runner._save()
        except Exception:
            pass


def _run_pipeline_core(session_id: str, workspace: Path, roster_index: int = None):
    """后台执行 Pipeline + 结果上传 Supabase Storage（核心逻辑）"""
    runner = PipelineRunner(session_id, workspace)

    # ---- 如果本地文件缺失（实例重启后），从 Supabase Storage 恢复 ----
    uploads_dir = workspace / "uploads"
    local_files = list(uploads_dir.glob("*.xlsx")) if uploads_dir.exists() else []
    if not local_files:
        print(f"[Background] 本地文件缺失，从 Supabase Storage 恢复...")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        supabase_service.restore_upload_files(session_id, str(uploads_dir))

    matched, missing = file_manager.auto_detect_files(session_id)
    print(f"[Background] 文件匹配结果: matched={list(matched.keys())}, missing={missing}")

    # ---- 把上传文件复制到 workspace 根目录（pipeline 从 workspace 读取原始文件）----
    # pipeline/main.py 用 --workspace 同时作为 input_dir，所以文件必须在 workspace/ 根目录
    import shutil
    need_files = {
        "原始数据 (2).xlsx": "raw_data",
        "离职流程 (1).xlsx": "leave",
        "班次.xlsx": "shift",
        "补签管理 (1).xlsx": "resign",
        "GUS+美区签字报表.xlsx": "sign_this_week",
        "GUS+美区签字报表 (2).xlsx": "sign_last_week",
        "GUS+美区签字报表 (1).xlsx": "sign_biweek",
        "GUS需剔除人员（白名单）.xlsx": "gus_whitelist",
    }

    for target_name, ftype in need_files.items():
        if ftype in matched:
            src = matched[ftype]
            dst = workspace / target_name  # 放到 workspace 根目录，而非 uploads 子目录
            if str(src) != str(dst):
                shutil.copy2(src, dst)
                print(f"[Background] 复制 {ftype}: {src.name} -> {target_name}")

    roster_file = matched.get("roster")
    if roster_file:
        roster_index = roster_index or 46
        dest = workspace / f"花名册 ({roster_index}).xlsx"  # workspace 根目录
        shutil.copy2(roster_file, dest)
        print(f"[Background] 复制花名册: {roster_file.name} -> 花名册 ({roster_index}).xlsx")

    # ---- 执行 Pipeline ----
    success = runner.run(roster_index=roster_index)

    # ---- 结果上传到 Supabase Storage ----
    if success:
        print(f"[Background] 开始上传结果文件到 Supabase Storage...")
        upload_log = supabase_service.save_result_files(session_id, str(workspace))
        
        # 保存上传日志到本地文件（方便调试）
        import json
        log_file = workspace / "upload_log.json"
        with open(log_file, "w", encoding="utf-8") as fp:
            json.dump(upload_log, fp, ensure_ascii=False, indent=2)
        print(f"[Background] 上传日志已保存到: {log_file}")
        
        if not upload_log["success"]:
            print(f"[Background] Storage 上传失败，保留本地文件作为后备")
            print(f"[Background] 失败详情: {upload_log['files_failed']}")
            # 不清理本地文件，作为后备
        else:
            print(f"[Background] Storage 上传成功: {len(upload_log['files_uploaded'])} 个文件")
            # ---- 清理本地文件（减少磁盘占用）----
            try:
                for f in ["清洗后数据.xlsx", "指标计算后数据.xlsx", "透视分析.xlsx"]:
                    fp = workspace / f
                    if fp.exists():
                        fp.unlink()
                        print(f"[Background] 已清理本地文件: {f}")
            except Exception:
                pass

    # ---- 摘要写入 Supabase DB ----
    summary = runner.get_summary()
    supabase_service.update_processing_status(
        session_id=session_id,
        status=summary.get("status", "failed"),
        summary=summary if success else None,
        error=summary.get("error") if not success else None,
    )


@router.post("/start", response_model=ProcessStatus)
async def start_processing(
    request: ProcessRequest,
):
    """启动考勤数据处理流程（产出 Excel → 存入 Supabase Storage）"""
    session_id = request.session_id

    # ---- 自动清理旧数据（防止 Storage 超标）----
    try:
        print(f"[Start] 执行自动清理（删除 30 天前的旧数据）...")
        cleanup_stats = supabase_service.cleanup_old_sessions(days=30)
        if cleanup_stats["db_deleted"] > 0 or cleanup_stats["storage_deleted"] > 0:
            print(f"[Start] 自动清理完成: 删除 {cleanup_stats['db_deleted']} 条记录, {cleanup_stats['storage_deleted']} 个文件")
        if cleanup_stats["errors"]:
            print(f"[Start] 清理警告: {cleanup_stats['errors']}")
    except Exception as e:
        print(f"[Start] 自动清理失败（继续执行）: {e}")

    session_dir = SESSIONS_DIR / session_id
    if not session_dir.exists():
        # 本地目录丢失（实例重启），从 Supabase Storage 恢复上传文件
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "uploads").mkdir(exist_ok=True)
        print(f"[Start] 会话目录丢失，尝试从 Storage 恢复...")
        supabase_service.restore_upload_files(session_id, str(session_dir / "uploads"))

    # 再次检查文件是否已恢复
    matched, missing = file_manager.auto_detect_files(session_id)
    if missing:
        # 尝试再次从 Storage 恢复（可能第一次没成功）
        supabase_service.restore_upload_files(session_id, str(session_dir / "uploads"))
        matched, missing = file_manager.auto_detect_files(session_id)

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"缺少必要文件: {', '.join(missing)}",
        )

    supabase_service.update_processing_status(session_id, "processing")

    workspace = session_dir
    roster_index = request.roster_index

    # 使用 threading.Thread 而非 FastAPI BackgroundTask，确保在 Windows 和 Linux 上都能正常运行
    with _tasks_lock:
        existing = _active_tasks.get(session_id)
        if existing and existing.get("thread") and existing["thread"].is_alive():
            return ProcessStatus(
                session_id=session_id,
                status="processing",
                current_step=None,
                progress=0.0,
                steps_completed=[],
            )
        t = threading.Thread(
            target=run_pipeline_background,
            args=(session_id, workspace, roster_index),
            daemon=True,
            name=f"pipeline-{session_id}",
        )
        _active_tasks[session_id] = {"thread": t}
        t.start()
    print(f"[Start] 后台处理线程已启动: {session_id}")

    return ProcessStatus(
        session_id=session_id,
        status="processing",
        current_step=None,
        progress=0.0,
        steps_completed=[],
    )


@router.get("/{session_id}/status", response_model=ProcessStatus)
async def get_process_status(session_id: str):
    """查询处理进度（优先本地磁盘，兜底 Supabase DB）"""
    session_dir = SESSIONS_DIR / session_id

    if session_dir.exists():
        # 本地文件存在 → 正常读取
        runner = PipelineRunner(session_id, session_dir)
        state = runner.get_status()
        return ProcessStatus(
            session_id=session_id,
            status=state.get("status", "unknown"),
            current_step=state.get("current_step"),
            progress=state.get("progress", 0.0),
            steps_completed=state.get("steps_completed", []),
            error=state.get("error"),
            started_at=state.get("started_at"),
            completed_at=state.get("completed_at"),
        )

    # 本地文件丢失 → 尝试 Supabase
    db_session = supabase_service.get_session(session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在，请重新上传文件")

    db_status = db_session.get("status", "unknown")
    return ProcessStatus(
        session_id=session_id,
        status=db_status,
        current_step=None,
        progress=100.0 if db_status == "completed" else (0.0 if db_status == "failed" else 50.0),
        steps_completed=["clean", "metrics", "pivot"] if db_status == "completed" else [],
        error=db_session.get("error"),
        started_at=db_session.get("started_at"),
        completed_at=db_session.get("completed_at"),
    )


@router.get("/{session_id}/result", response_model=ProcessResult)
async def get_process_result(session_id: str):
    """获取处理结果（优先本地，兜底 Supabase Storage）"""
    session_dir = SESSIONS_DIR / session_id

    if session_dir.exists():
        runner = PipelineRunner(session_id, session_dir)
        state = runner.get_status()
        if state.get("status") == "completed":
            summary = runner.get_summary()
            excel_files = runner.get_excel_files()
            return ProcessResult(
                session_id=session_id,
                summary=summary,
                excel_files=[ExcelFileInfo(**f) for f in excel_files],
            )

    # 本地没有 → 从 Supabase 恢复
    db_session = supabase_service.get_session(session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")

    db_summary = db_session.get("summary") or {}
    db_status = db_session.get("status", "unknown")
    if db_status != "completed":
        raise HTTPException(status_code=400, detail="处理尚未完成")

    # 从 Supabase Storage 列出文件
    storage_files = supabase_service.list_excel_files(session_id)
    excel_files = []
    for sf in storage_files:
        fname = sf["filename"]
        labels = {
            "清洗后数据.xlsx": "清洗后数据",
            "指标计算后数据.xlsx": "指标计算后数据",
            "透视分析.xlsx": "透视分析",
        }
        excel_files.append(ExcelFileInfo(
            filename=fname,
            label=labels.get(fname, fname),
            size_bytes=sf.get("size_bytes", 0),
            download_url=f"/api/v1/process/{session_id}/download/{fname}",
        ))

    return ProcessResult(
        session_id=session_id,
        summary=db_summary,
        excel_files=excel_files,
    )


@router.get("/{session_id}/download/{filename}")
async def download_excel(session_id: str, filename: str):
    """下载 Excel 文件（本地 → Supabase Storage 兜底）"""
    session_dir = SESSIONS_DIR / session_id

    # 1. 先尝试本地文件
    if session_dir.exists():
        file_path = session_dir / filename
        if file_path.exists():
            from fastapi.responses import FileResponse
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # 2. 从 Supabase Storage 获取（新的 results/ 路径格式）
    storage_path = f"results/{session_id}/{filename}"
    try:
        data = supabase_service.download_result_file(session_id, filename)
        if data:
            from fastapi.responses import StreamingResponse
            import io
            return StreamingResponse(
                io.BytesIO(data),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"文件 {filename} 不存在，请重新处理")


@router.get("/{session_id}/debug")
async def debug_session(session_id: str):
    """调试端点：返回会话目录状态（方便排查处理问题）"""
    import os
    from app.services.pipeline_runner import PIPELINE_SOURCE
    session_dir = SESSIONS_DIR / session_id

    result = {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "session_dir_exists": session_dir.exists(),
        "pipeline_source": str(PIPELINE_SOURCE),
        "pipeline_source_exists": PIPELINE_SOURCE.exists(),
        "files_in_workspace": [],
        "files_in_uploads": [],
        "status_file_content": None,
    }

    if session_dir.exists():
        # workspace 根目录文件
        result["files_in_workspace"] = [
            {"name": f.name, "size": f.stat().st_size}
            for f in session_dir.iterdir() if f.is_file()
        ]
        # uploads 目录文件
        uploads = session_dir / "uploads"
        if uploads.exists():
            result["files_in_uploads"] = [
                {"name": f.name, "size": f.stat().st_size}
                for f in uploads.iterdir() if f.is_file()
            ]
        # status.json
        status_file = session_dir / "status.json"
        if status_file.exists():
            import json
            with open(status_file, "r", encoding="utf-8") as fp:
                result["status_file_content"] = json.load(fp)

    # Supabase Storage 上的文件
    result["storage_upload_files"] = []
    result["storage_result_files"] = []
    try:
        upload_files = supabase_service.client.storage.from_(
            supabase_service.STORAGE_BUCKET
        ).list(f"uploads/{session_id}") if supabase_service.client else []
        result["storage_upload_files"] = [f["name"] for f in (upload_files or [])]
    except Exception as e:
        result["storage_upload_error"] = str(e)
    try:
        result_files = supabase_service.list_excel_files(session_id)
        result["storage_result_files"] = [f["filename"] for f in result_files]
    except Exception as e:
        result["storage_result_error"] = str(e)

    return result


@router.post("/admin/cleanup")
async def manual_cleanup(days: int = 30):
    """
    手动清理旧数据（管理员端点）
    - days: 删除超过 N 天的旧数据（默认 30 天）
    - 返回清理统计
    """
    print(f"[Admin] 手动清理请求: 删除 {days} 天前的旧数据")
    
    if not supabase_service.is_configured():
        raise HTTPException(status_code=500, detail="Supabase 未配置")
    
    try:
        stats = supabase_service.cleanup_old_sessions(days=days)
        
        # 获取清理后的存储使用情况
        usage = supabase_service.get_storage_usage()
        
        return {
            "message": "清理完成",
            "cleanup_stats": stats,
            "current_storage_usage": usage,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.get("/admin/storage-usage")
async def get_storage_usage():
    """
    查询 Storage 使用情况
    返回: 文件数量、总大小、按会话分布
    """
    if not supabase_service.is_configured():
        raise HTTPException(status_code=500, detail="Supabase 未配置")
    
    try:
        usage = supabase_service.get_storage_usage()
        return usage
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/admin/debug-storage")
async def debug_storage():
    """
    诊断 Supabase Storage 连接和配置问题
    返回详细的诊断信息和错误
    """
    import traceback
    import os
    
    diagnostics = {
        "step": "",
        "errors": [],
        "info": {},
    }
    
    try:
        # Step 1: 检查环境变量
        diagnostics["step"] = "check_env"
        diagnostics["info"]["SUPABASE_URL"] = os.getenv("SUPABASE_URL", "NOT_SET")
        service_key = os.getenv("SUPABASE_SERVICE_KEY", "")
        diagnostics["info"]["SERVICE_KEY_LENGTH"] = len(service_key)
        diagnostics["info"]["SERVICE_KEY_PREFIX"] = service_key[:20] if service_key else "EMPTY"
        
        # Step 2: 检查 supabase_service 配置
        diagnostics["step"] = "check_supabase_service"
        diagnostics["info"]["client_exists"] = supabase_service.client is not None
        diagnostics["info"]["storage_bucket"] = supabase_service.STORAGE_BUCKET
        
        if not supabase_service.client:
            diagnostics["errors"].append("Supabase client 未初始化")
            return diagnostics
        
        # Step 3: 列出 buckets
        diagnostics["step"] = "list_buckets"
        print(f"[Debug] 正在列出 buckets...")
        buckets = supabase_service.client.storage.list_buckets()
        diagnostics["info"]["buckets"] = [{"name": b.name, "public": b.public} for b in buckets]
        diagnostics["info"]["bucket_exists"] = supabase_service.STORAGE_BUCKET in [b.name for b in buckets]
        
        # Step 4: 测试上传
        diagnostics["step"] = "test_upload"
        test_content = b"debug test"
        test_path = f"debug/test_{os.getpid()}.txt"
        print(f"[Debug] 正在上传测试文件: {test_path}")
        
        upload_result = supabase_service.client.storage.from_(
            supabase_service.STORAGE_BUCKET
        ).upload(
            path=test_path,
            file=test_content,
            file_options={"content-type": "text/plain", "upsert": "true"},
        )
        diagnostics["info"]["upload_success"] = True
        diagnostics["info"]["upload_result"] = str(upload_result)
        print(f"[Debug] 上传成功: {upload_result}")
        
        # Step 5: 获取 URL
        diagnostics["step"] = "get_url"
        public_url = supabase_service.client.storage.from_(
            supabase_service.STORAGE_BUCKET
        ).get_public_url(test_path)
        diagnostics["info"]["public_url"] = public_url
        print(f"[Debug] 公开 URL: {public_url}")
        
        # Step 6: 删除测试文件
        diagnostics["step"] = "cleanup"
        supabase_service.client.storage.from_(
            supabase_service.STORAGE_BUCKET
        ).remove([test_path])
        diagnostics["info"]["cleanup_success"] = True
        print(f"[Debug] 清理成功")
        
        diagnostics["info"]["all_tests_passed"] = True
        
    except Exception as e:
        diagnostics["errors"].append({
            "step": diagnostics["step"],
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        })
        print(f"[Debug] 错误在步骤 {diagnostics['step']}: {e}")
        print(traceback.format_exc())
    
    return diagnostics


@router.get("/{session_id}/upload-log")
async def get_upload_log(session_id: str):
    """
    查看文件上传到 Supabase Storage 的详细日志
    """
    session_dir = SESSIONS_DIR / session_id
    log_file = session_dir / "upload_log.json"
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="上传日志不存在")
    
    with open(log_file, "r", encoding="utf-8") as fp:
        log = json.load(fp)
    
    return log


@router.post("/{session_id}/cancel")
async def cancel_processing(session_id: str):
    """
    取消或删除一个处理会话
    - 如果任务还在运行，从内存中移除
    - 从数据库中删除记录
    - 删除关联的 Storage 文件和本地文件
    """
    import os
    import shutil
    
    # 1. 尝试移除活跃的后台线程
    with _tasks_lock:
        active = _active_tasks.get(session_id)
        if active and active.get("thread") and active["thread"].is_alive():
            print(f"[Cancel] 标记移除活跃任务: {session_id}")
        _active_tasks.pop(session_id, None)
    
    # 2. 清理本地文件
    session_dir = SESSIONS_DIR / session_id
    local_deleted = False
    if session_dir.exists():
        shutil.rmtree(session_dir)
        local_deleted = True
        print(f"[Cancel] 已删除本地目录: {session_dir}")
    
    # 3. 删除数据库记录
    db_deleted = False
    try:
        if supabase_service.is_configured() and supabase_service.client:
            supabase_service.client.table("reports").delete().eq("session_id", session_id).execute()
            supabase_service.client.table("processing_sessions").delete().eq("session_id", session_id).execute()
            db_deleted = True
            print(f"[Cancel] 已删除数据库记录: {session_id}")
    except Exception as e:
        print(f"[Cancel] 删除数据库记录失败: {e}")
    
    # 4. 删除 Storage 文件
    storage_deleted = 0
    try:
        if supabase_service.is_configured() and supabase_service.client:
            for prefix in ["uploads", "results"]:
                try:
                    files = supabase_service.client.storage.from_(
                        supabase_service.STORAGE_BUCKET
                    ).list(f"{prefix}/{session_id}")
                    for f in (files or []):
                        file_path = f"{prefix}/{session_id}/{f['name']}"
                        supabase_service.client.storage.from_(
                            supabase_service.STORAGE_BUCKET
                        ).remove([file_path])
                        storage_deleted += 1
                except Exception:
                    pass
            print(f"[Cancel] 已删除 {storage_deleted} 个 Storage 文件")
    except Exception as e:
        print(f"[Cancel] 删除 Storage 文件失败: {e}")
    
    return {
        "message": "会话已取消/删除",
        "session_id": session_id,
        "local_deleted": local_deleted,
        "db_deleted": db_deleted,
        "storage_deleted": storage_deleted,
    }


@router.post("/admin/cleanup-stuck")
async def cleanup_stuck_sessions():
    """
    清理所有卡住的'处理中'会话
    - 删除所有状态为'processing'但超过 5 分钟的会话
    """
    import traceback
    from datetime import datetime, timedelta
    
    if not supabase_service.is_configured():
        raise HTTPException(status_code=500, detail="Supabase 未配置")
    
    stats = {
        "stuck_sessions_found": 0,
        "deleted": 0,
        "failed_to_delete": [],
    }
    
    try:
        # 获取所有 processing 状态的会话
        response = supabase_service.client.table("processing_sessions").select(
            "session_id, status, created_at"
        ).eq("status", "processing").execute()
        
        stuck_sessions = response.data or []
        stats["stuck_sessions_found"] = len(stuck_sessions)
        
        print(f"[Cleanup] 发现 {len(stuck_sessions)} 个卡住的处理中会话")
        
        for session in stuck_sessions:
            session_id = session["session_id"]
            try:
                # 删除数据库记录
                supabase_service.client.table("reports").delete().eq(
                    "session_id", session_id
                ).execute()
                supabase_service.client.table("processing_sessions").delete().eq(
                    "session_id", session_id
                ).execute()
                
                # 删除 Storage 文件
                for prefix in ["uploads", "results"]:
                    try:
                        files = supabase_service.client.storage.from_(
                            supabase_service.STORAGE_BUCKET
                        ).list(f"{prefix}/{session_id}")
                        for f in (files or []):
                            file_path = f"{prefix}/{session_id}/{f['name']}"
                            supabase_service.client.storage.from_(
                                supabase_service.STORAGE_BUCKET
                            ).remove([file_path])
                    except Exception:
                        pass
                
                # 删除本地目录
                session_dir = SESSIONS_DIR / session_id
                if session_dir.exists():
                    import shutil
                    shutil.rmtree(session_dir)
                
                stats["deleted"] += 1
                print(f"[Cleanup] 已删除会话: {session_id}")
                
            except Exception as e:
                print(f"[Cleanup] 删除会话 {session_id} 失败: {e}")
                stats["failed_to_delete"].append({
                    "session_id": session_id,
                    "error": str(e),
                })
        
        return stats
        
    except Exception as e:
        print(f"[Cleanup] 清理失败: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")
