"""
步骤2: 指标计算
输入: 清洗后数据.xlsx + 班次.xlsx
输出: 指标计算后数据.xlsx

规则说明:
  规则0: 休息开始时间、休息结束时间（与班次字典匹配）
  规则1: HUB标记（部门含.H或等于EWR.G/CNO.G）
  规则2: 是否排班正确（7级优先级判断）
  规则3: 每日总工时计算 = 原公式值 + 居家办公合计（审批中）
  规则4: 日超8H = max(0, 每日总工时计算 - 8)
  规则5: 是否排班、标准打卡数、缺卡数
  规则6: 备注请假/出差/居家办公覆盖 - 时长≥8H覆盖标准打卡数为0+排班正确；时长≥4H覆盖标准打卡数为2+打卡<2则不正确
"""
import os
import re
import pandas as pd
import numpy as np
from datetime import timedelta

from pipeline.utils import (
    to_str, to_num, parse_hm, abs_diff_minutes,
    total_hours, parse_work_period,
)


# ============================================================
# 业务规则函数 (公开以便测试导入)
# ============================================================

# ---- 规则0: 休息开始时间、休息结束时间 ----
def get_rest_times(shift_name, shift_dict):
    """从班次字典获取休息时间"""
    entry = shift_dict.get(to_str(shift_name), {})
    return entry.get('休息开始时间', ''), entry.get('休息结束时间', '')


# ---- 规则1: HUB ----
def get_hub(row):
    """判断是否HUB人员"""
    d4 = to_str(row.get('四级部门', ''))
    d5 = to_str(row.get('五级部门', ''))
    if '.H' in d5 or '.H' in d4 or d5 == 'EWR.G' or d5 == 'CNO.G':
        return 'hub'
    return ''


# ---- 规则2: 是否排班正确（6级优先级） ----
def get_correct(row):
    """
    是否排班正确的6级优先级判断

    优先级:
      1. 班次名称为空 → /
      2. 休息日/节假日 + 首末均为空 → 正确
      3. 班次不为空 + 末打卡为空 + |首打卡-班次上班| ≤ 1h → 正确
      4. 休息日/节假日 + 单边打卡 → 不正确
      5. 非休息日 + 首末均有 + |首打卡-班次上班| ≤ 1h → 正确
      6. 其他 → 不正确

    注: 原P3(非休息日+首打卡为空→判断末打卡与下班时间差)已删除，
        首打卡为空直接落入兜底→不正确。
    """
    first   = to_str(row.get('首打卡时间', ''))
    last    = to_str(row.get('末打卡时间', ''))
    shift   = to_str(row.get('班次名称', ''))
    start_t = to_str(row.get('班次上班时间', ''))
    end_t   = to_str(row.get('班次下班时间', ''))

    # P1: 班次名称为空 → /
    if shift == '':
        return '/'

    is_rest = 'TY_休息日' in shift or 'TY_美国节假日' in shift

    # P2: 休息日/节假日 + 首末打卡均为空 → 正确
    if is_rest and first == '' and last == '':
        return '正确'

    # P3 (原P4): 班次不为空 + 末打卡为空 + |首打卡-班次上班| ≤ 1h → 正确
    if shift != '' and last == '':
        diff = abs_diff_minutes(first, start_t)
        if diff is not None and diff <= 60:
            return '正确'
        return '不正确'

    # P4 (原P5): 休息日/节假日 + 单边打卡 → 不正确
    if is_rest:
        if (first == '' and last != '') or (first != '' and last == ''):
            return '不正确'

    # P5 (原P6): 非休息日 + 首末均有 + |首打卡-班次上班| ≤ 1h → 正确
    if not is_rest and first != '' and last != '':
        diff_start = abs_diff_minutes(first, start_t)
        if diff_start is not None and diff_start <= 60:
            return '正确'
        return '不正确'

    # P6 (原P7): 其他 → 不正确
    return '不正确'


# ---- 规则3: 每日总工时计算 ----
def get_daily_total(row, df_columns, daily_total_col_name=None):
    """
    每日总工时计算 = 原公式值 + 居家办公合计（审批中）

    参数:
        row: 数据行
        df_columns: DataFrame列名列表(用于匹配3种变体)
        daily_total_col_name: 已匹配到的列名(优化: 调用方先匹配)
    """
    if daily_total_col_name is None:
        for col in ['每日总工时(公式：末打卡-首打卡-班次午休时间+居家办公时长)合计',
                    '每日总工时(公式：末打卡时间-首打卡时间-班次午休时间+居家办公时长)合计',
                    '每日总工时(公式：末打卡时间-首打卡时间-班次午休时间+居家办公时长)']:
            if col in df_columns:
                daily_total_col_name = col
                break

    daily_total = to_num(row.get(daily_total_col_name, 0)) if daily_total_col_name else 0.0
    home_office_pending = to_num(row.get('居家办公合计（审批中）', 0))
    return round(daily_total + home_office_pending, 2)


# ---- 规则4: 日超8H ----
def get_over8h(daily_total):
    """
    日超8H = max(0, 每日总工时计算 - 8)
    返回 (日超8H值, 是否日超8H)
    """
    value = max(0.0, round(daily_total - 8, 2))
    flag = '是' if value > 0 else '否'
    return value, flag


# ---- 规则5: 标准打卡数 ----
def get_standard_count(row, is_correct, shift_name, note):
    """
    计算标准打卡数

    优先级:
      1. 未排班 → 0 (v26)
      2. 休息日/节假日 → 0
      3. 备注为空 → 4
      4. 解析备注时间段失败 → 4
      5. 时间段完全吻合班次起止 → 0 (最高优先级)
      6. 按"排班正确/不正确"分支计算
    """
    is_scheduled = to_str(shift_name) != ''
    is_rest_or_holiday = 'TY_休息日' in to_str(shift_name) or 'TY_美国节假日' in to_str(shift_name)
    is_note_empty = to_str(note) == ''

    # 1: 未排班 → 0
    if not is_scheduled:
        return 0
    # 2: 休息日/节假日 → 0
    if is_rest_or_holiday:
        return 0
    # 3: 备注为空 → 4
    if is_note_empty:
        return 4
    # 3.5: v27 过期(仅已废弃/已撤回, 不含审批中/已完成) → 视为无备注
    if _is_note_expired(note):
        return 4
    # 4: 解析备注时间段
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

    # 优先规则: 出差/请假时间段与班次起止时间完全吻合 → 0
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


# ---- 辅助: 判断备注是否已过期 ----
NOTE_ACTIVE = re.compile(r'\[(?:审批中|已完成)\]')
NOTE_EXPIRED = re.compile(r'\[(?:已废弃|已撤回)\]')

def _is_note_expired(note):
    """
    判断备注是否已过期，不参与规则6覆盖。
    优先级: [审批中]/[已完成] > [已废弃]/[已撤回]
    含 [审批中] 或 [已完成] → 有效（不视为过期）
    仅含 [已废弃] 或 [已撤回] 且无有效状态 → 过期
    """
    if NOTE_ACTIVE.search(note):
        return False
    return bool(NOTE_EXPIRED.search(note))


# ---- 规则6: 备注请假/出差/居家办公覆盖排班正确和标准打卡数 ----
def apply_note_override(row, current_correct, current_std_count):
    """
    备注为请假/休假/出差/居家办公时，根据时长覆盖排班正确和标准打卡数

    规则:
      - 含[已废弃]/[已撤回]且无[审批中]/[已完成]的不覆盖（v27）
      - 时长 ≥ 8H → 标准打卡数 = 0，排班正确 = "正确"
      - 时长 ≥ 4H → 标准打卡数 = 2；若班次内打卡次数 < 2 → 排班正确 = "不正确"
      - 仅当新值与原值不同时才覆盖

    返回 (new_correct, new_std_count)
    """
    note = to_str(row.get('备注（GF）', ''))
    if not note:
        return current_correct, current_std_count

    # v27: 过期状态不覆盖
    if _is_note_expired(note):
        return current_correct, current_std_count

    # 判断是否请假/出差/居家办公等类型
    NOTE_LEAVE_TYPES = r'居家办公|公出|出差|病假|年假|无薪病假|事假|调休|婚假|产假|陪产假|丧假|工伤假'
    if not re.search(NOTE_LEAVE_TYPES, note):
        return current_correct, current_std_count

    period = parse_work_period(note)
    if period is None:
        return current_correct, current_std_count

    period_start, period_end = period
    duration_hours = (period_end - period_start).total_seconds() / 3600

    new_correct = current_correct
    new_std_count = current_std_count
    actual_punches = to_num(row.get('班次内打卡次数', 0))

    if duration_hours >= 8:
        new_std_count = 0
        new_correct = '正确'
    elif duration_hours >= 4:
        new_std_count = 2
        if actual_punches < 2:
            new_correct = '不正确'

    return new_correct, new_std_count


# ============================================================
# 执行函数
# ============================================================

def run(config):
    """执行指标计算"""
    cleaned_file = config['cleaned_file']
    shift_file   = config['shift_file']
    output_file  = config['metrics_file']

    # ============================================================
    # 1. 读取数据
    # ============================================================
    df = pd.read_excel(cleaned_file, dtype=str)
    shift_df = pd.read_excel(shift_file, dtype=str)

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

    # 提前匹配"每日总工时"列名（3种变体）
    daily_total_col_name = None
    for col in ['每日总工时(公式：末打卡-首打卡-班次午休时间+居家办公时长)合计',
                '每日总工时(公式：末打卡时间-首打卡时间-班次午休时间+居家办公时长)合计',
                '每日总工时(公式：末打卡时间-首打卡时间-班次午休时间+居家办公时长)']:
        if col in df.columns:
            daily_total_col_name = col
            break
    print(f"每日总工时列名: {daily_total_col_name or '未找到'}")

    # ============================================================
    # 2. 逐行处理
    # ============================================================
    records = []
    for idx, row in df.iterrows():
        r = row.to_dict()
        shift_name = to_str(r.get('班次名称', ''))
        note       = to_str(r.get('备注（GF）', ''))

        rs, re_ = get_rest_times(shift_name, shift_dict)
        hub = get_hub(r)
        correct = get_correct(row)
        daily_total = get_daily_total(row, df.columns, daily_total_col_name)
        over8h_value, over8h_flag = get_over8h(daily_total)
        is_scheduled = '是' if shift_name != '' else '否'
        std_count = get_standard_count(row, correct, shift_name, note)
        actual_count = to_num(r.get('班次内打卡次数', 0))

        # 规则6: 备注请假/出差覆盖（仅当与原值不同时覆盖）
        override_correct, override_std = apply_note_override(row, correct, std_count)
        if override_correct != correct or override_std != std_count:
            correct = override_correct
            std_count = override_std

        miss_count = max(0.0, std_count - actual_count)

        r['_休息开始时间'] = rs
        r['_休息结束时间'] = re_
        r['_HUB'] = hub
        r['_是否排班正确'] = correct
        r['_每日总工时计算'] = daily_total
        r['日超8H'] = over8h_value
        r['_是否日超8H'] = over8h_flag
        r['_是否排班'] = is_scheduled
        r['_标准打卡数'] = std_count
        r['_缺卡数'] = miss_count
        records.append(r)

    result_df = pd.DataFrame(records)

    # ============================================================
    # 3. 构建输出列顺序
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

    # 规则5: 是否排班、标准打卡数、缺卡数 → 班次内打卡次数后
    pc_idx = cols_out.index('班次内打卡次数')
    cols_out.insert(pc_idx + 1, '__是否排班__')
    cols_out.insert(pc_idx + 2, '__标准打卡数__')
    cols_out.insert(pc_idx + 3, '__缺卡数__')

    rename_map = {
        '__休息开始时间__': '休息开始时间',
        '__休息结束时间__': '休息结束时间',
        '__HUB__': 'HUB',
        '__是否排班正确__': '是否排班正确',
        '__每日总工时计算__': '每日总工时计算',
        '__是否日超8H__': '是否日超8H',
        '__是否排班__': '是否排班',
        '__标准打卡数__': '标准打卡数',
        '__缺卡数__': '缺卡数',
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
    # 4. 输出
    # ============================================================
    out_df.to_excel(output_file, index=False)
    print(f"\n输出: {output_file}")
    print(f"输出数据: {len(out_df)}行, {len(out_df.columns)}列")
    print(f"\n=== 统计 ===")
    for col in ['是否排班正确', '是否日超8H', '是否排班', 'HUB']:
        if col in out_df.columns:
            print(f"  {col}: {out_df[col].value_counts().to_dict()}")
