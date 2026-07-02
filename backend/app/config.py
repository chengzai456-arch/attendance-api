"""
考勤平台后端配置
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

# Storage
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
SESSIONS_DIR = DATA_DIR / "sessions"
REPORTS_DIR = DATA_DIR / "reports"

for d in [DATA_DIR, UPLOAD_DIR, SESSIONS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Pipeline source - where the attendance-pipeline scripts live
PIPELINE_DIR = Path(os.getenv("PIPELINE_DIR", BASE_DIR / "pipeline"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,https://localhost:3000").split(",")

# File size limit (50MB)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024

# Session cleanup (keep for 30 days)
SESSION_RETENTION_DAYS = 30
