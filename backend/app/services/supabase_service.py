"""
Supabase 交互服务 - 存储处理记录和报告数据
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY


class SupabaseService:
    """封装 Supabase 交互"""

    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            print("[Supabase] 未配置 SUPABASE_URL/SERVICE_KEY，跳过初始化")
            return
        try:
            from supabase import create_client, Client
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        except Exception as e:
            print(f"[Supabase] 初始化失败: {e}")

    def is_configured(self) -> bool:
        return self.client is not None

    def create_processing_record(self, session_id: str, date: str,
                                  files_uploaded: List[str]) -> Optional[dict]:
        """创建处理记录"""
        if not self.client:
            return None
        try:
            result = self.client.table("processing_sessions").insert({
                "session_id": session_id,
                "date": date,
                "status": "uploaded",
                "files_uploaded": files_uploaded,
                "created_at": datetime.now().isoformat(),
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[Supabase] 创建记录失败: {e}")
            return None

    def update_processing_status(self, session_id: str, status: str,
                                  summary: Optional[dict] = None,
                                  error: Optional[str] = None) -> Optional[dict]:
        """更新处理状态"""
        if not self.client:
            return None
        try:
            update_data = {"status": status}
            if summary:
                update_data["summary"] = summary
                update_data["completed_at"] = datetime.now().isoformat()
            if error:
                update_data["error"] = error
            result = self.client.table("processing_sessions").update(update_data).eq(
                "session_id", session_id
            ).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[Supabase] 更新状态失败: {e}")
            return None

    def save_report(self, session_id: str, report_json: dict) -> Optional[dict]:
        """保存报告数据"""
        if not self.client:
            return None
        try:
            result = self.client.table("reports").insert({
                "session_id": session_id,
                "report_data": report_json,
                "created_at": datetime.now().isoformat(),
            }).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[Supabase] 保存报告失败: {e}")
            return None

    def get_history(self, limit: int = 20) -> List[dict]:
        """获取处理历史"""
        if not self.client:
            return []
        try:
            result = self.client.table("processing_sessions").select("*").order(
                "created_at", desc=True
            ).limit(limit).execute()
            return result.data or []
        except Exception as e:
            print(f"[Supabase] 查询历史失败: {e}")
            return []

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取单个会话记录"""
        if not self.client:
            return None
        try:
            result = self.client.table("processing_sessions").select("*").eq(
                "session_id", session_id
            ).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[Supabase] 查询会话失败: {e}")
            return None

    def get_report(self, session_id: str) -> Optional[dict]:
        """获取报告数据"""
        if not self.client:
            return None
        try:
            result = self.client.table("reports").select("*").eq(
                "session_id", session_id
            ).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[Supabase] 查询报告失败: {e}")
            return None

    def save_clean_data(self, session_id: str, data: List[dict]) -> Optional[int]:
        """保存清洗后数据到 Supabase（大表写入）"""
        if not self.client:
            return None
        try:
            batch_size = 500
            total = 0
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                for row in batch:
                    row["session_id"] = session_id
                self.client.table("attendance_data").insert(batch).execute()
                total += len(batch)
            return total
        except Exception as e:
            print(f"[Supabase] 保存清洗数据失败: {e}")
            return None

    # ------ Storage 文件操作 ------

    STORAGE_BUCKET = "attendance-results"
    UPLOAD_PREFIX = "uploads"
    RESULT_PREFIX = "results"

    def _ensure_bucket(self):
        """确保 Storage bucket 存在"""
        if not self.client:
            print("[Supabase] client 未初始化，跳过 bucket 检查")
            return False
        try:
            buckets = self.client.storage.list_buckets()
            names = [b.name for b in buckets]
            print(f"[Supabase] 现有 buckets: {names}")
            if self.STORAGE_BUCKET not in names:
                print(f"[Supabase] 创建 bucket: {self.STORAGE_BUCKET}")
                self.client.storage.create_bucket(
                    self.STORAGE_BUCKET,
                    options={"public": True},
                )
                print(f"[Supabase] bucket 创建成功")
            return True
        except Exception as e:
            print(f"[Supabase] Storage bucket 检查/创建失败: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def save_upload_file(self, session_id: str, filename: str, file_bytes: bytes) -> Optional[str]:
        """保存上传的原始文件到 Supabase Storage（处理前备份）"""
        if not self.client:
            print("[Supabase] client 未初始化，跳过上传备份")
            return None
        try:
            bucket_ok = self._ensure_bucket()
            if not bucket_ok:
                print(f"[Supabase] bucket 检查失败，但继续尝试上传备份...")
            storage_path = f"{self.UPLOAD_PREFIX}/{session_id}/{filename}"
            print(f"[Supabase] 备份上传文件到 {storage_path} ({len(file_bytes)} bytes)")
            self.client.storage.from_(self.STORAGE_BUCKET).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "upsert": "true"},
            )
            print(f"[Supabase] 备份上传成功: {storage_path}")
            return storage_path
        except Exception as e:
            print(f"[Supabase] 保存上传文件失败: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def restore_upload_files(self, session_id: str, target_dir: str) -> bool:
        """从 Supabase Storage 恢复上传文件到本地目录（实例重启后）"""
        import os
        if not self.client:
            return False
        try:
            os.makedirs(target_dir, exist_ok=True)
            files = self.client.storage.from_(self.STORAGE_BUCKET).list(f"{self.UPLOAD_PREFIX}/{session_id}")
            if not files:
                print(f"[Supabase] 未找到上传文件: uploads/{session_id}")
                return False
            for f in files:
                fname = f["name"]
                storage_path = f"{self.UPLOAD_PREFIX}/{session_id}/{fname}"
                try:
                    data = self.client.storage.from_(self.STORAGE_BUCKET).download(storage_path)
                    if data:
                        fpath = os.path.join(target_dir, fname)
                        with open(fpath, "wb") as fp:
                            fp.write(data)
                except Exception as de:
                    print(f"[Supabase] 下载 {fname} 失败: {de}")
            return True
        except Exception as e:
            print(f"[Supabase] 恢复上传文件失败: {e}")
            return False

    def save_excel_file(self, session_id: str, filename: str, file_bytes: bytes) -> Optional[str]:
        """上传 Excel 结果文件到 Supabase Storage"""
        if not self.client:
            print("[Supabase] client 未初始化，跳过上传")
            return None
        try:
            # 尝试创建 bucket，失败也不影响后续上传（如果 bucket 已存在）
            bucket_ok = self._ensure_bucket()
            if not bucket_ok:
                print(f"[Supabase] bucket 检查失败，但继续尝试上传...")

            storage_path = f"{self.RESULT_PREFIX}/{session_id}/{filename}"
            print(f"[Supabase] 上传文件到 {storage_path} ({len(file_bytes)} bytes)")
            self.client.storage.from_(self.STORAGE_BUCKET).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "upsert": "true"},
            )
            url = self.client.storage.from_(self.STORAGE_BUCKET).get_public_url(storage_path)
            print(f"[Supabase] 上传成功: {url}")
            return url
        except Exception as e:
            print(f"[Supabase] 保存 Excel 文件失败: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def list_excel_files(self, session_id: str) -> List[dict]:
        """列出会话的所有 Excel 结果文件"""
        if not self.client:
            return []
        try:
            files = self.client.storage.from_(self.STORAGE_BUCKET).list(f"{self.RESULT_PREFIX}/{session_id}")
            result = []
            for f in files:
                fname = f["name"]
                storage_path = f"{self.RESULT_PREFIX}/{session_id}/{fname}"
                url = self.client.storage.from_(self.STORAGE_BUCKET).get_public_url(storage_path)
                result.append({
                    "filename": fname,
                    "size_bytes": f.get("metadata", {}).get("size", 0),
                    "url": url,
                })
            return result
        except Exception as e:
            print(f"[Supabase] 列出文件失败: {e}")
            return []

    def download_result_file(self, session_id: str, filename: str) -> Optional[bytes]:
        """从 Supabase Storage 下载结果文件"""
        if not self.client:
            return None
        try:
            storage_path = f"{self.RESULT_PREFIX}/{session_id}/{filename}"
            return self.client.storage.from_(self.STORAGE_BUCKET).download(storage_path)
        except Exception as e:
            print(f"[Supabase] 下载结果文件失败: {e}")
            return None

    def save_result_files(self, session_id: str, workspace: str) -> dict:
        """
        保存处理产出的 Excel 文件到 Supabase Storage
        返回详细的上传日志
        """
        import os
        excel_names = ["清洗后数据.xlsx", "指标计算后数据.xlsx", "透视分析.xlsx"]
        log = {
            "session_id": session_id,
            "workspace": workspace,
            "files_checked": [],
            "files_uploaded": [],
            "files_failed": [],
            "success": False,
        }
        
        for fname in excel_names:
            fpath = os.path.join(workspace, fname)
            fpath_info = {
                "filename": fname,
                "path": fpath,
                "exists": os.path.exists(fpath),
                "size": os.path.getsize(fpath) if os.path.exists(fpath) else 0,
            }
            log["files_checked"].append(fpath_info)
            
            if os.path.exists(fpath):
                try:
                    with open(fpath, "rb") as fp:
                        file_bytes = fp.read()
                        print(f"[Supabase] 准备上传 {fname} ({len(file_bytes)} bytes)")
                        
                        url = self.save_excel_file(session_id, fname, file_bytes)
                        if url:
                            log["files_uploaded"].append({
                                "filename": fname,
                                "size": len(file_bytes),
                                "url": url,
                            })
                            print(f"[Supabase] {fname} 上传成功: {url}")
                        else:
                            log["files_failed"].append({
                                "filename": fname,
                                "error": "save_excel_file returned None",
                            })
                            print(f"[Supabase] {fname} 上传失败: save_excel_file returned None")
                except Exception as e:
                    log["files_failed"].append({
                        "filename": fname,
                        "error": str(e),
                    })
                    print(f"[Supabase] {fname} 上传异常: {e}")
            else:
                print(f"[Supabase] 文件不存在: {fpath}")
        
        log["success"] = len(log["files_uploaded"]) > 0
        print(f"[Supabase] 上传总结: {len(log['files_uploaded'])}/{len(excel_names)} 成功, {len(log['files_failed'])} 失败")
        return log

    def cleanup_old_sessions(self, days: int = 30) -> dict:
        """
        清理超过指定天数的旧数据（数据库记录 + Storage 文件）
        返回清理统计: {"db_deleted": N, "storage_deleted": N, "errors": []}
        """
        if not self.client:
            return {"db_deleted": 0, "storage_deleted": 0, "errors": ["Supabase 未配置"]}
        
        import traceback
        stats = {"db_deleted": 0, "storage_deleted": 0, "errors": [], "sessions_deleted": []}
        
        try:
            # 1. 查找超过 N 天的已完成会话
            from datetime import timedelta
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            print(f"[Cleanup] 查找 {days} 天前的旧数据 (截止: {cutoff_date})")
            
            old_sessions = self.client.table("processing_sessions").select("session_id, created_at").lt(
                "created_at", cutoff_date
            ).execute()
            
            if not old_sessions.data:
                print(f"[Cleanup] 没有找到超过 {days} 天的旧数据")
                return stats
            
            old_session_ids = [s["session_id"] for s in old_sessions.data]
            print(f"[Cleanup] 找到 {len(old_session_ids)} 个旧会话: {old_session_ids[:5]}...")
            
            # 2. 删除 Storage 中的文件（uploads 和 results）
            for session_id in old_session_ids:
                try:
                    # 删除 uploads/{session_id}/
                    try:
                        upload_files = self.client.storage.from_(self.STORAGE_BUCKET).list(f"{self.UPLOAD_PREFIX}/{session_id}")
                        for f in (upload_files or []):
                            file_path = f"{self.UPLOAD_PREFIX}/{session_id}/{f['name']}"
                            self.client.storage.from_(self.STORAGE_BUCKET).remove([file_path])
                            stats["storage_deleted"] += 1
                    except Exception as e:
                        print(f"[Cleanup] 删除 uploads/{session_id} 失败: {e}")
                    
                    # 删除 results/{session_id}/
                    try:
                        result_files = self.client.storage.from_(self.STORAGE_BUCKET).list(f"{self.RESULT_PREFIX}/{session_id}")
                        for f in (result_files or []):
                            file_path = f"{self.RESULT_PREFIX}/{session_id}/{f['name']}"
                            self.client.storage.from_(self.STORAGE_BUCKET).remove([file_path])
                            stats["storage_deleted"] += 1
                    except Exception as e:
                        print(f"[Cleanup] 删除 results/{session_id} 失败: {e}")
                    
                    stats["sessions_deleted"].append(session_id)
                    
                except Exception as e:
                    err_msg = f"清理会话 {session_id} 失败: {str(e)}"
                    print(f"[Cleanup] {err_msg}")
                    stats["errors"].append(err_msg)
            
            # 3. 删除数据库记录（processing_sessions 和 reports）
            for session_id in old_session_ids:
                try:
                    # 删除 reports
                    self.client.table("reports").delete().eq("session_id", session_id).execute()
                    # 删除 processing_sessions
                    self.client.table("processing_sessions").delete().eq("session_id", session_id).execute()
                    stats["db_deleted"] += 1
                except Exception as e:
                    err_msg = f"删除数据库记录 {session_id} 失败: {str(e)}"
                    print(f"[Cleanup] {err_msg}")
                    stats["errors"].append(err_msg)
            
            print(f"[Cleanup] 完成: 删除 {stats['db_deleted']} 条记录, {stats['storage_deleted']} 个文件")
            return stats
            
        except Exception as e:
            err_msg = f"清理失败: {str(e)}"
            print(f"[Cleanup] {err_msg}")
            print(traceback.format_exc())
            stats["errors"].append(err_msg)
            return stats

    def get_storage_usage(self) -> dict:
        """
        获取 Storage 使用情况（估算）
        返回: {"total_files": N, "total_size_mb": M, "by_session": {...}}
        """
        if not self.client:
            return {"error": "Supabase 未配置"}
        
        try:
            total_size = 0
            total_files = 0
            by_session = {}
            
            # 列出所有 uploads 文件
            try:
                upload_sessions = self.client.storage.from_(self.STORAGE_BUCKET).list(self.UPLOAD_PREFIX)
                for session in (upload_sessions or []):
                    session_id = session["name"]
                    files = self.client.storage.from_(self.STORAGE_BUCKET).list(f"{self.UPLOAD_PREFIX}/{session_id}")
                    session_size = sum(f.get("metadata", {}).get("size", 0) for f in (files or []))
                    total_size += session_size
                    total_files += len(files or [])
                    by_session[session_id] = {"upload_files": len(files or []), "upload_size_mb": round(session_size / 1024 / 1024, 2)}
            except Exception as e:
                print(f"[Storage] 统计 uploads 失败: {e}")
            
            # 列出所有 results 文件
            try:
                result_sessions = self.client.storage.from_(self.STORAGE_BUCKET).list(self.RESULT_PREFIX)
                for session in (result_sessions or []):
                    session_id = session["name"]
                    files = self.client.storage.from_(self.STORAGE_BUCKET).list(f"{self.RESULT_PREFIX}/{session_id}")
                    session_size = sum(f.get("metadata", {}).get("size", 0) for f in (files or []))
                    total_size += session_size
                    total_files += len(files or [])
                    if session_id not in by_session:
                        by_session[session_id] = {}
                    by_session[session_id]["result_files"] = len(files or [])
                    by_session[session_id]["result_size_mb"] = round(session_size / 1024 / 1024, 2)
            except Exception as e:
                print(f"[Storage] 统计 results 失败: {e}")
            
            return {
                "total_files": total_files,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "total_size_gb": round(total_size / 1024 / 1024 / 1024, 3),
                "by_session": by_session,
            }
            
        except Exception as e:
            return {"error": str(e)}


supabase_service = SupabaseService()
