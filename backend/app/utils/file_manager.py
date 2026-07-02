"""
文件上传管理
"""
import uuid
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from app.config import UPLOAD_DIR, SESSIONS_DIR
from app.models.schemas import FileType


EXPECTED_FILES = {
    FileType.RAW_DATA: {
        "keywords": ["每日打卡", "工时推送", "原始数据"],
        "required": True,
        "description": "原始考勤打卡数据",
    },
    FileType.LEAVE: {
        "keywords": ["离职流程", "离职"],
        "required": True,
        "description": "离职人员流程",
    },
    FileType.ROSTER: {
        "keywords": ["花名册"],
        "required": True,
        "description": "在职人员花名册",
    },
    FileType.SHIFT: {
        "keywords": ["班次"],
        "required": True,
        "description": "班次字典",
    },
    FileType.RESIGN: {
        "keywords": ["补签管理", "补签"],
        "required": True,
        "description": "补签管理记录",
    },
    FileType.GUS_WHITELIST: {
        "keywords": ["GUS需剔除", "GUS白名单", "白名单"],
        "required": False,
        "description": "GUS白名单（非必填）",
    },
    # 签字报表通过特殊逻辑匹配，见 _match_sign_reports()
    FileType.SIGN_THIS_WEEK: {
        "keywords": ["本周加班", "本周"],
        "required": True,
        "description": "本周加班签字报表",
    },
    FileType.SIGN_LAST_WEEK: {
        "keywords": ["上周加班", "上周"],
        "required": True,
        "description": "上周加班签字报表",
    },
    FileType.SIGN_BIWEEK: {
        "keywords": ["双周累计", "双周"],
        "required": True,
        "description": "双周累计工时签字报表",
    },
}

# 签字报表基础关键词（文件名包含其中一个则认为是签字报表）
SIGN_REPORT_KEYWORDS = ["签字报表", "美区签字", "GUS+美区"]


def _extract_bracket_number(filename: str) -> Optional[int]:
    """提取文件名中括号里的数字，如 '报表 (2).xlsx' → 2，'报表.xlsx' → None"""
    m = re.search(r'\((\d+)\)', filename)
    return int(m.group(1)) if m else None


def _match_sign_reports(fnames: List[str]) -> Dict[str, str]:
    """
    智能匹配签字报表三种：
    - 无括号序号（或最大序号）→ 本周 (sign_this_week)
    - 序号 (2)              → 上周 (sign_last_week)
    - 序号 (1)              → 双周 (sign_biweek)

    也支持文件名含 本周/上周/双周 关键词的情况。
    """
    result = {}

    # 先尝试文件名关键词匹配
    for fname in fnames:
        if any(kw in fname for kw in ["本周加班", "本周"]):
            result["sign_this_week"] = fname
        elif any(kw in fname for kw in ["上周加班", "上周"]):
            result["sign_last_week"] = fname
        elif any(kw in fname for kw in ["双周累计", "双周"]):
            result["sign_biweek"] = fname

    # 找出所有签字报表文件（用于括号序号匹配）
    sign_files = [f for f in fnames if any(kw in f for kw in SIGN_REPORT_KEYWORDS)]
    if not sign_files:
        return result

    # 尚未通过关键词匹配的类型，用括号序号匹配
    unmatched_files = [f for f in sign_files if f not in result.values()]
    if not unmatched_files:
        return result

    # 按括号序号分组
    with_num = {f: _extract_bracket_number(f) for f in unmatched_files}
    no_num = [f for f, n in with_num.items() if n is None]
    num_2 = [f for f, n in with_num.items() if n == 2]
    num_1 = [f for f, n in with_num.items() if n == 1]

    # 无括号 → 本周
    if "sign_this_week" not in result and no_num:
        result["sign_this_week"] = no_num[0]
    # (2) → 上周
    if "sign_last_week" not in result and num_2:
        result["sign_last_week"] = num_2[0]
    # (1) → 双周
    if "sign_biweek" not in result and num_1:
        result["sign_biweek"] = num_1[0]

    return result


class FileManager:
    """管理上传文件和会话目录"""

    def __init__(self):
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> str:
        """创建新的处理会话"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        session_dir = SESSIONS_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "uploads").mkdir(exist_ok=True)
        return session_id

    def save_file(self, session_id: str, filename: str, content: bytes) -> Path:
        """保存上传文件到会话目录"""
        session_dir = SESSIONS_DIR / session_id / "uploads"
        session_dir.mkdir(parents=True, exist_ok=True)

        file_path = session_dir / filename
        file_path.write_bytes(content)
        return file_path

    def auto_detect_files(self, session_id: str) -> Tuple[Dict[str, Path], List[str]]:
        """
        自动检测上传文件类型
        返回: (file_type -> path 映射, 缺失文件列表)
        """
        session_dir = SESSIONS_DIR / session_id / "uploads"
        uploaded = list(session_dir.glob("*.xlsx")) + list(session_dir.glob("*.xls"))

        matched: Dict[str, Path] = {}
        available = {p.name: p for p in uploaded}
        fname_list = list(available.keys())

        # ---- 非签字报表：普通关键词匹配 ----
        sign_types = {FileType.SIGN_THIS_WEEK, FileType.SIGN_LAST_WEEK, FileType.SIGN_BIWEEK}
        remaining = set(fname_list)

        for ftype, info in EXPECTED_FILES.items():
            if ftype in sign_types:
                continue
            for fname in list(remaining):
                if any(kw in fname for kw in info["keywords"]):
                    matched[ftype.value] = session_dir / fname
                    remaining.discard(fname)
                    break

        # ---- 签字报表：智能括号序号匹配 ----
        sign_matched = _match_sign_reports(list(remaining) + fname_list)
        for ftype_val, fname in sign_matched.items():
            if fname in available:
                matched[ftype_val] = session_dir / fname

        missing = [
            ftype.value for ftype, info in EXPECTED_FILES.items()
            if info["required"] and ftype.value not in matched
        ]

        return matched, missing

    def get_session_files(self, session_id: str) -> List[Path]:
        """获取会话所有文件"""
        session_dir = SESSIONS_DIR / session_id / "uploads"
        if not session_dir.exists():
            return []
        return list(session_dir.glob("*.xlsx")) + list(session_dir.glob("*.xls"))

    def get_session_dir(self, session_id: str) -> Path:
        """获取会话工作目录"""
        session_dir = SESSIONS_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def cleanup_session(self, session_id: str):
        """清理会话文件"""
        session_dir = SESSIONS_DIR / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)

    @staticmethod
    def get_pipeline_file_map(matched: Dict[str, Path]) -> Dict[str, str]:
        """
        将自动检测的文件映射转换为 pipeline config 期望的路径格式
        """
        mapping = {
            "原始数据 (2).xlsx": matched.get("raw_data"),
            "离职流程 (1).xlsx": matched.get("leave"),
            "班次.xlsx": matched.get("shift"),
            "补签管理 (1).xlsx": matched.get("resign"),
            "GUS+美区签字报表.xlsx": matched.get("sign_this_week"),
            "GUS+美区签字报表 (2).xlsx": matched.get("sign_last_week"),
            "GUS+美区签字报表 (1).xlsx": matched.get("sign_biweek"),
        }

        if "gus_whitelist" in matched:
            mapping["GUS需剔除人员（白名单）.xlsx"] = matched["gus_whitelist"]

        return {k: str(v) for k, v in mapping.items() if v is not None}


file_manager = FileManager()
