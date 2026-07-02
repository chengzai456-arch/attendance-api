"""
考勤分析共享工具函数
从原始 scripts/ 提取，消除跨脚本重复
"""
import sys
import os

# 强制 UTF-8 输出，解决 Windows Git Bash 中文乱码
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import re
import pandas as pd
from datetime import datetime, timedelta


# ============================================================
# 类型转换
# ============================================================

def to_str(v):
    """安全字符串转换，处理 nan/None/空值"""
    if v is None:
        return ''
    s = str(v).strip()
    return '' if s in ('nan', 'NaT', 'None', 'NaN', 'nat', '') else s


def to_num(v):
    """安全数值转换，非数值返回 0.0"""
    try:
        return float(to_str(v))
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# 时间解析
# ============================================================

def parse_hm(s):
    """解析 HH:MM 或 HH:MM:SS 或带日期前缀的时间，返回 timedelta"""
    s = to_str(s).strip()
    if not s:
        return None
    # 去掉日期前缀 (如 "1900-01-01 09:30:00")
    if ' ' in s or '-' in s:
        parts = s.replace('1900-01-01 ', '').strip().split(':')
    else:
        parts = s.split(':')
    try:
        h, m = int(parts[0]), int(parts[1])
        return timedelta(hours=h, minutes=m)
    except (ValueError, IndexError):
        return None


def abs_diff_minutes(t1, t2):
    """两个时间字符串的绝对差（分钟）"""
    p1, p2 = parse_hm(t1), parse_hm(t2)
    if p1 is None or p2 is None:
        return None
    return abs((p1 - p2).total_seconds() / 60)


def total_hours(hms_str):
    """字符串工时 → 小时数（兼容 Excel 天数格式和 HH:MM 格式）"""
    s = to_str(hms_str)
    if s == '':
        return 0.0
    try:
        # Excel 天数格式 (如 "0.5" 表示 12 小时)
        f = float(s)
        return round(f * 24, 2)
    except ValueError:
        pass
    try:
        # HH:MM 格式
        parts = s.split(':')
        return int(parts[0]) + int(parts[1]) / 60
    except (ValueError, IndexError):
        return 0.0


# ============================================================
# 日期 / 时间段解析
# ============================================================

def parse_date(s):
    """多格式日期解析"""
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d', '%Y-%m-%d', '%m/%d/%Y']:
        try:
            return pd.to_datetime(s, format=fmt)
        except (ValueError, TypeError):
            pass
    try:
        return pd.to_datetime(s)
    except (ValueError, TypeError):
        return pd.NaT


def parse_work_period(s):
    """
    解析备注(GF)中的时间段，返回 (start_td, end_td) 或 None

    支持格式:
      - "居家办公09:30-18:00"
      - "出差申请2026/05/19 09:30-2026/05/19 18:00[审批中]"
      - "公出", "病假", "年假", "无薪病假", "事假", "调休", "婚假", "产假" 等同理
    """
    s = to_str(s)
    if not s:
        return None
    # 使用 .*? 跳过日期等中间内容，支持更多请假类型
    m = re.search(
        r'(?:居家办公|公出|出差|病假|年假|无薪病假|事假|调休|婚假|产假|陪产假|丧假|工伤假).*?(\d{1,2}:\d{2})-.*?(\d{1,2}:\d{2})',
        s
    )
    if m:
        sh, sm = int(m.group(1).split(':')[0]), int(m.group(1).split(':')[1])
        eh, em = int(m.group(2).split(':')[0]), int(m.group(2).split(':')[1])
        start = timedelta(hours=sh, minutes=sm)
        end   = timedelta(hours=eh, minutes=em)
        # 跨日处理：结束时间 < 开始时间 → 加 24h
        if end <= start:
            end += timedelta(hours=24)
        return start, end
    return None


# ============================================================
# 数值计算
# ============================================================

def safe_div(a, b):
    """安全除法，分母为0返回 0"""
    return round(a / b, 4) if b else 0.0


def pct_str(v, decimals=0):
    """比率转百分比字符串，默认四舍五入到整数，补签率用 decimals=1"""
    if decimals == 0:
        return f"{int(round(v * 100))}%"
    return f"{round(v * 100, decimals)}%"
