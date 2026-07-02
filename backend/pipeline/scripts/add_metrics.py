"""
考勤指标计算脚本 - 规则0~5
输入: 清洗后数据.xlsx + 班次.xlsx
输出: 指标计算后数据.xlsx

规则说明:
  规则0: 休息开始时间、休息结束时间（与班次字典匹配）
  规则1: HUB标记（部门含.H或等于EWR.G/CNO.G）
  规则2: 是否排班正确（7级优先级判断）
  规则3: 每日总工时计算（原公式+居家办公审批中）
  规则4: 是否日超8H
  规则5: 是否排班、标准打卡数、缺卡次数（v4: 正则跳过日期 + 排班完全吻合→0优先）
"""
import sys, os, re
sys.path.insert(0, r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages")
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============================================================
# 配置区（按需修改）
# ============================================================
WORKSPACE  = r"C:\Users\Administrator\WorkBuddy\2026-05-21-18-13-22"  # 替换 {workspace}
CLEAN_FILE = os.path.join(WORKSPACE, "清洗后数据.xlsx")
SHIFT_FILE = r"D:\Documents\Downloads\班次.xlsx"
OUTPUT_FILE = os.path.join(WORKSPACE, "指标计算后数据.xlsx")

# ============================================================
# 工具函数
# ============================================================
def to_str(v):
    if v is None: return ''
    s = str(v).strip()
    return '' if s in ('nan', 'NaT', 'None', 'NaN', 'nat', '') else s

def to_num(v):
    try: return float(to_str(v))
    except: return 0.0

def parse_hm(s):
    """解析 HH:MM 或 HH:MM:SS 或带日期前缀的时间，返回 timedelta"""
    s = to_str(s).strip()
    if not s: return None
    if ' ' in s or '-' in s:
        parts = s.replace('1900-01-01 ', '').strip().split(':')
    else:
        parts = s.split(':')
    try:
        h, m = int(parts[0]), int(parts[1])
        return timedelta(hours=h, minutes=m)
    except:
        return None

def abs_diff_minutes(t1, t2):
    p1, p2 = parse_hm(t1), parse_hm(t2)
    if p1 is None or p2 is None: return None
    return abs((p1 - p2).total_seconds() / 60)

def total_hours(hms_str):
    s = to_str(hms_str)
    if s == '': return 0.0
    try:
        f = float(s)
        return round(f * 24, 2)
    except: pass
    try:
        parts = s.split(':')
        return int(parts[0]) + int(parts[1]) / 60
    except: return 0.0

def parse_work_period(s):
    """解析备注(GF)中的时间段，返回 (start_td, end_td) 或 None"""
    s = to_str(s)
    if not s: return None
    # v4: 使用 .*? 代替 [^\d]*，允许跳过日期等中间内容（如 "出差申请2026/05/19 09:30-2026/05/19 18:00[审批中]"）
    m = re.search(r'(?:居家办公|公出|出差|病假|年假|无薪病假).*?(\d{1,2}:\d{2})-.*?(\d{1,2}:\d{2})', s)
    if m:
        sh, sm = int(m.group(1).split(':')[0]), int(m.group(1).split(':')[1])
        eh, em = int(m.group(2).split(':')[0]), int(m.group(2).split(':')[1])
        return timedelta(hours=sh, minutes=sm), timedelta(hours=eh, minutes=em)
    return None

# ============================================================
# 1. 读取数据
# ============================================================
df = pd.read_excel(CLEAN_FILE, dtype=str)
shift_df = pd.read_excel(SHIFT_FILE, dtype=str)

print(f"清洗后数据: {len(df)}行, {len(df.columns)}列")
print(f"列名: {df.columns.tolist()}")
print(f"班次文件: {len(shift_df)}行")

# 构建班次字典
shift_dict = {}
for _, row in shift_df.iterrows():
    name = to_str(row.get('班次名称', ''))
    if name:
        shift_dict[name] = {
            '休息开始时间': to_str(row.get('休息开始时间', '')),
            '休息结束时间': to_str(row.get('休息结束时间', '')),
        }
print(f"班次字典条目: {len(shift_dict)}")

# ============================================================
# 2. 规则函数
# ============================================================

# ---- 规则0: 休息开始时间、休息结束时间 ----
def get_rest_times(shift_name):
    entry = shift_dict.get(to_str(shift_name), {})
    return entry.get('休息开始时间', ''), entry.get('休息结束时间', '')

# ---- 规则1: HUB ----
def get_hub(row):
    d4 = to_str(row.get('四级部门', ''))
    d5 = to_str(row.get('五级部门', ''))
    if '.H' in d5 or '.H' in d4 or d5 == 'EWR.G' or d5 == 'CNO.G':
        return 'hub'
    return ''

# ---- 规则2: 是否排班正确（8级优先级，2026-05-25优化版 v3） ----
# 规则变更说明（相比旧版）：
#   - 旧P2"首末均为空→正确"缩小为仅休息日/节假日适用
#   - 旧P3/P4"首/末为空→不正确"改为检查时间差（|末-下班|≤1h / |首-上班|≤1h）
#   - 新增P2专用于休息日+双空场景，P5专用于休息日+单边场景
#   - P3(v3): 非休息日 + 首打卡为空 + |末打卡-班次下班| ≤ 1h → 正确；否则不正确
#             （允许首打卡缺失时靠末打卡判断）
#   - P6(v3): 非休息日+双非空+|首打卡-上班|≤1h（不再兼顾末打卡）→ 正确
#             （收紧规则：首末均有打卡时，必须首打卡符合才算正确）
#   - P7: 其他所有情况 → 不正确
def get_correct(row):
    first   = to_str(row.get('首打卡时间', ''))
    last    = to_str(row.get('末打卡时间', ''))
    shift   = to_str(row.get('班次名称', ''))
    start_t = to_str(row.get('班次上班时间', ''))
    end_t   = to_str(row.get('班次下班时间', ''))

    # 优先级1(最高): 班次名称为空 → /
    if shift == '':
        return '/'

    is_rest = 'TY_休息日' in shift or 'TY_美国节假日' in shift

    # 优先级2: 休息日/节假日 + 首末打卡均为空 → 正确
    if is_rest and first == '' and last == '':
        return '正确'

    # 优先级3(v3): 非休息日 + 首打卡为空 + |末打卡-班次下班| ≤ 1h → 正确；否则不正确
    # （首打卡缺失时，末打卡符合下班时间才算正确）
    if not is_rest and first == '':
        diff = abs_diff_minutes(last, end_t)
        if diff is not None and diff <= 60:
            return '正确'
        return '不正确'

    # 优先级4: 班次不为空 + 末打卡为空 → |首打卡-班次上班| ≤ 1小时 → 正确；否则不正确
    if shift != '' and last == '':
        diff = abs_diff_minutes(first, start_t)
        if diff is not None and diff <= 60:
            return '正确'
        return '不正确'

    # 优先级5: 休息日/节假日 + 单边打卡（首空末不空 或 首不空末空）→ 不正确
    # 注意：P3/P4已拦截首/末为空的所有情况（含非休息日），此处仅当上面未命中时生效
    if is_rest:
        if (first == '' and last != '') or (first != '' and last == ''):
            return '不正确'

    # 优先级6(v3): 非休息日 + 首末打卡均不为空 + |首打卡-班次上班| ≤ 1h → 正确
    # （收紧：首末均有时，只看首打卡是否符合上班时间，不再兼顾末打卡）
    if not is_rest and first != '' and last != '':
        diff_start = abs_diff_minutes(first, start_t)
        if diff_start is not None and diff_start <= 60:
            return '正确'
        return '不正确'

    # 优先级7: 其他情况（含非休息日双空等）→ 不正确
    return '不正确'

# ---- 规则3: 每日总工时计算 ----
def get_daily_total(row):
    daily_total = 0.0
    for col in ['每日总工时(公式：末打卡-首打卡-班次午休时间+居家办公时长)合计',
                '每日总工时(公式：末打卡时间-首打卡时间-班次午休时间+居家办公时长)合计',
                '每日总工时(公式：末打卡时间-首打卡时间-班次午休时间+居家办公时长)']:
        if col in df.columns:
            daily_total = to_num(row.get(col, 0))
            break
    home_office = to_num(row.get('居家办公合计（审批中）', 0))
    return round(daily_total + home_office, 2)

# ---- 规则4: 是否日超8H ----
def get_over8h(row):
    v = to_num(row.get('日超8H', 0))
    return '是' if v != 0 else '否'

# ---- 规则5: 标准打卡数 ----
def get_standard_count(row, is_correct, shift_name, note):
    is_scheduled = to_str(shift_name) != ''
    is_rest_or_holiday = 'TY_休息日' in to_str(shift_name) or 'TY_美国节假日' in to_str(shift_name)
    is_note_empty = to_str(note) == ''

    # 5.2① 是否排班=否 → 4
    if not is_scheduled:
        return 4
    # 5.2② 休息日/节假日 → 0
    if is_rest_or_holiday:
        return 0
    # 5.2③ 备注为空 → 4
    if is_note_empty:
        return 4
    # 5.2④ 解析备注时间段
    period = parse_work_period(to_str(note))
    if period is None:
        return 4

    period_start, period_end = period
    shift_start = parse_hm(to_str(row.get('班次上班时间', '')))
    shift_end   = parse_hm(to_str(row.get('班次下班时间', '')))
    rest_start  = parse_hm(to_str(row.get('休息开始时间', '')))
    rest_end    = parse_hm(to_str(row.get('休息结束时间', '')))

    if shift_start is None or shift_end is None:
        return 4

    period_hours = (period_end - period_start).total_seconds() / 3600

    # 优先规则(v4, 最高优先级): 出差/请假时间段与班次起止时间完全吻合 → 0
    if period_start == shift_start and period_end == shift_end:
        return 0

    if is_correct == '正确':
        # 【排班正确=正确】
        if rest_start is not None and rest_end is not None:
            # 完全在休息区间内 → 0
            if period_start >= rest_start and period_end <= rest_end:
                return 0
            # 与休息交叉(只交叉不包含) → 3
            elif (period_start < rest_end and period_end > rest_start and
                  not (period_start <= rest_start and period_end >= rest_end) and
                  period_start >= shift_start and period_end <= shift_end):
                return 3
            # 完全包含休息区间 → 2
            elif (period_start <= rest_start and period_end >= rest_end and
                  period_start >= shift_start and period_end <= shift_end):
                return 2
            else:
                return 4
        else:
            return 4
    else:
        # 【排班正确=不正确】
        if period_hours >= 7:
            return 0
        elif period_hours >= 4:
            return 2
        else:
            return 4

# ============================================================
# 3. 逐行处理
# ============================================================
records = []
for idx, row in df.iterrows():
    r = row.to_dict()
    shift_name = to_str(r.get('班次名称', ''))
    note       = to_str(r.get('备注（GF）', ''))

    rs, re_ = get_rest_times(shift_name)
    hub = get_hub(r)
    correct = get_correct(row)
    daily_total = get_daily_total(row)
    over8h = get_over8h(row)
    is_scheduled = '是' if shift_name != '' else '否'
    std_count = get_standard_count(row, correct, shift_name, note)
    actual_count = to_num(r.get('班次内打卡次数', 0))
    miss_count = max(0.0, std_count - actual_count)

    r['_休息开始时间'] = rs
    r['_休息结束时间'] = re_
    r['_HUB'] = hub
    r['_是否排班正确'] = correct
    r['_每日总工时计算'] = daily_total
    r['_是否日超8H'] = over8h
    r['_是否排班'] = is_scheduled
    r['_标准打卡数'] = std_count
    r['_缺卡次数'] = miss_count
    records.append(r)

result_df = pd.DataFrame(records)

# ============================================================
# 4. 构建输出列顺序（在原始列中指定位置插入新增列）
# ============================================================
cols_out = list(df.columns)

# 规则0: 休息开始时间、休息结束时间 → 班次名称后
sm_idx = cols_out.index('班次名称')
cols_out.insert(sm_idx + 1, '__休息开始时间__')
cols_out.insert(sm_idx + 2, '__休息结束时间__')

# 规则1: HUB → 五级部门后
d5_idx = cols_out.index('五级部门')
cols_out.insert(d5_idx + 1, '__HUB__')

# 规则2: 是否排班正确 → 末打卡时间后
lp_idx = cols_out.index('末打卡时间')
cols_out.insert(lp_idx + 1, '__是否排班正确__')

# 规则3: 每日总工时计算 → 居家办公合计（审批中）后
ho_idx = cols_out.index('居家办公合计（审批中）')
cols_out.insert(ho_idx + 1, '__每日总工时计算__')

# 规则4: 是否日超8H → 日超8H后
o8_idx = cols_out.index('日超8H')
cols_out.insert(o8_idx + 1, '__是否日超8H__')

# 规则5: 是否排班、标准打卡数、缺卡次数 → 班次内打卡次数后
pc_idx = cols_out.index('班次内打卡次数')
cols_out.insert(pc_idx + 1, '__是否排班__')
cols_out.insert(pc_idx + 2, '__标准打卡数__')
cols_out.insert(pc_idx + 3, '__缺卡次数__')

# 构建输出DataFrame
rename_map = {
    '__休息开始时间__': '休息开始时间',
    '__休息结束时间__': '休息结束时间',
    '__HUB__': 'HUB',
    '__是否排班正确__': '是否排班正确',
    '__每日总工时计算__': '每日总工时计算',
    '__是否日超8H__': '是否日超8H',
    '__是否排班__': '是否排班',
    '__标准打卡数__': '标准打卡数',
    '__缺卡次数__': '缺卡次数',
}

out_data = {}
for c in cols_out:
    if c in result_df.columns:
        out_data[c] = result_df[c]
    elif c in rename_map:
        src_key = '_' + c.replace('__', '')
        if src_key in result_df.columns:
            out_data[c] = result_df[src_key]

out_df = pd.DataFrame(out_data)
out_df.rename(columns=rename_map, inplace=True)

# ============================================================
# 5. 输出
# ============================================================
out_df.to_excel(OUTPUT_FILE, index=False)
print(f"\n输出: {OUTPUT_FILE}")
print(f"输出数据: {len(out_df)}行, {len(out_df.columns)}列")
print(f"\n=== 统计 ===")
for col in ['是否排班正确', '是否日超8H', '是否排班', 'HUB']:
    if col in out_df.columns:
        print(f"  {col}: {out_df[col].value_counts().to_dict()}")

