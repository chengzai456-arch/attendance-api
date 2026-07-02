"""
考勤数据处理平台 - FastAPI 后端
"""
import sys
from pathlib import Path

# 确保项目根目录在 Python path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS, DATA_DIR
from app.routers import files, pipeline, reports


app = FastAPI(
    title="考勤数据处理平台 API",
    description="考勤排班数据分析全流程处理平台，支持文件上传、数据清洗、指标计算、透视分析和HTML报告生成",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(files.router)
app.include_router(pipeline.router)
app.include_router(reports.router)


@app.get("/")
async def root():
    return {
        "name": "考勤数据处理平台",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "data_dir": str(DATA_DIR),
        "disk_usage": _get_disk_usage(),
    }


def _get_disk_usage():
    try:
        import psutil
        usage = psutil.disk_usage(str(DATA_DIR))
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": usage.percent,
        }
    except Exception:
        return {"error": "无法获取磁盘信息"}
