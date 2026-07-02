"""
考勤数据清洗脚本
输入: 原始数据.xlsx, 离职流程.xlsx, 花名册 (N).xlsx
输出: 清洗后数据.xlsx

清洗步骤（严格按顺序执行）：
  步骤1: 剔除离职人员（最后工作日 < 标准日期；若审批状态有值则额外要求含 审批中/已完成/转交）
  步骤2: 剔除未入职人员（入职日期 > 标准日期）
  步骤3: GL00工号处理（先剔除 GL502563，再仅保留白名单）
  步骤4: 剔除 EU人力资源部
"""
import sys
sys.path.insert(0, r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages")
import pandas as pd
import numpy as np
from datetime import datetime

# ============================================================
# 配置区（按需修改）
# ============================================================
RAW_PATH    = r"D:\Documents\Downloads\原始数据.xlsx"
LEAVE_PATH  = r"D:\Documents\Downloads\离职流程.xlsx"
ROSTER_PATH = r"D:\Documents\Downloads\花名册 (12).xlsx"
OUTPUT_DIR  = r"C:\Users\Administrator\WorkBuddy\{workspace}"  # 替换 {workspace} 为实际路径
OUTPUT_FILE = "清洗后数据.xlsx"

# ============================================================
# 工具函数
# ============================================================
def parse_date(s):
    """多格式日期解析"""
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d', '%Y-%m-%d', '%m/%d/%Y']:
        try:
            return pd.to_datetime(s, format=fmt)
        except:
            pass
    try:
        return pd.to_datetime(s)
    except:
        return pd.NaT

# ============================================================
# 1. 读取文件
# ============================================================
df_raw   = pd.read_excel(RAW_PATH, header=0, dtype=str)
df_leave = pd.read_excel(LEAVE_PATH, header=0, dtype=str)
df_roster = pd.read_excel(ROSTER_PATH, header=0, dtype=str)

# 去掉第一行重复列头
if str(df_raw.iloc[0].get('考勤日期', '')).strip() == '考勤日期':
    df_raw = df_raw.iloc[1:].reset_index(drop=True)

print(f"原始数据行数: {len(df_raw)}")

# ============================================================
# 2. 识别标准日期
# ============================================================
date_col = '考勤日期'
df_raw[date_col] = df_raw[date_col].astype(str).str.strip()

non_empty = df_raw[
    df_raw[date_col].notna() &
    (df_raw[date_col] != '') & (df_raw[date_col] != 'nan') & (df_raw[date_col] != 'NaT')
]
parsed_dates = non_empty[date_col].apply(parse_date).dropna().unique()
standard_dates = sorted([d for d in parsed_dates if pd.notna(d)])
standard_date = max(standard_dates) if len(standard_dates) > 1 else standard_dates[0]
print(f"标准日期: {standard_date.date()}")

# ============================================================
# 3. 步骤1: 剔除离职流程
# ============================================================
# 注意: 当离职流程表的审批状态列全部为空时，仅按"最后工作日 < 标准日期"判断
# 如果审批状态列有值，则仍需审批状态含 审批中/已完成/转交
df_leave['_last_work_date'] = df_leave['最后工作日'].apply(parse_date)
has_status = df_leave['审批状态'].notna().any() and df_leave['审批状态'].apply(lambda x: str(x).strip() not in ['', 'nan', 'None']).any()
if has_status:
    leave_status_filter = ['审批中', '已完成', '转交']
    df_leave['_status_valid'] = df_leave['审批状态'].apply(
        lambda x: any(s in str(x) for s in leave_status_filter) if pd.notna(x) else False
    )
    leave_to_remove = df_leave[
        (df_leave['_last_work_date'] < standard_date) &
        (df_leave['_status_valid'] == True)
    ]['工号'].dropna().unique()
    print(f"步骤1 - 离职剔除(含审批状态过滤): {len(leave_to_remove)}个工号")
else:
    # 审批状态全为空，仅按最后工作日判断
    leave_to_remove = df_leave[
        df_leave['_last_work_date'] < standard_date
    ]['工号'].dropna().unique()
    print(f"步骤1 - 离职剔除(审批状态为空，仅按最后工作日): {len(leave_to_remove)}个工号")
before = len(df_raw)
df_raw = df_raw[~df_raw['工号'].isin(leave_to_remove)]
print(f"  剔除后: {len(df_raw)} (减少 {before - len(df_raw)} 行)")

# ============================================================
# 4. 步骤2: 剔除未入职
# ============================================================
df_roster['_join_date'] = df_roster['入职日期'].apply(parse_date)
roster_to_remove = df_roster[
    df_roster['_join_date'] > standard_date
]['工号'].dropna().unique()
print(f"步骤2 - 未入职剔除: {len(roster_to_remove)}个工号")
before = len(df_raw)
df_raw = df_raw[~df_raw['工号'].isin(roster_to_remove)]
print(f"  剔除后: {len(df_raw)} (减少 {before - len(df_raw)} 行)")

# ============================================================
# 5. 步骤3: GL00工号处理
# ============================================================
whitelist = {'GL000434', 'GL001344', 'GL000004', 'GL000440', 'GL000446', 'GL000902', 'GL001183'}
extra_remove = {'GL502563'}

before = len(df_raw)
df_raw = df_raw[~df_raw['工号'].isin(extra_remove)]
print(f"步骤3a - 剔除GL502563后: {len(df_raw)} (减少 {before - len(df_raw)} 行)")

is_gl00 = df_raw['工号'].str.startswith('GL00', na=False)
not_whitelist = ~df_raw['工号'].isin(whitelist)
mask_remove = is_gl00 & not_whitelist
before = len(df_raw)
df_raw = df_raw[~mask_remove]
print(f"步骤3b - GL00非白名单剔除: {len(df_raw)} (减少 {before - len(df_raw)} 行)")

# ============================================================
# 6. 步骤4: 剔除 EU人力资源部
# ============================================================
before = len(df_raw)
df_raw = df_raw[df_raw['三级部门'].str.strip() != 'EU人力资源部']
print(f"步骤4 - EU人力资源部剔除: {len(df_raw)} (减少 {before - len(df_raw)} 行)")

# ============================================================
# 7. 输出
# ============================================================
import os
out_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
os.makedirs(OUTPUT_DIR, exist_ok=True)
df_raw.to_excel(out_path, index=False)
print(f"\n输出: {out_path}")
print(f"最终行数: {len(df_raw)}")
