"""
生成 HTML 报告所需的完整 JSON 数据（含穿透明细）
输入: 指标计算后数据.xlsx
输出: report_data.json

JSON 结构:
  - meta: 元数据（总人数、日期）
  - overview: 全公司汇总（各指标计数 + 穿透工号列表）
  - departments[]: 按三级部门分组
    - summary: 三级汇总（含穿透工号列表）
    - sub_depts[]: 四级明细
      - summary: 四级汇总（含穿透工号列表）
      - detail: 各指标明细
"""
import sys, os, json
sys.path.insert(0, r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages")
import pandas as pd
import numpy as np

# ============================================================
# 配置区
# ============================================================
WORKSPACE  = r"C:\Users\Administrator\WorkBuddy\2026-05-21-18-13-22"
INPUT_FILE = os.path.join(WORKSPACE, "指标计算后数据.xlsx")
OUTPUT_FILE = os.path.join(WORKSPACE, "report_data.json")

# ============================================================
# 工具函数
# ============================================================
def ts(v):
    if v is None: return ''
    s = str(v).strip()
    return '' if s in ('nan', 'NaT', 'None', 'NaN') else s

def tn(v):
    try: return float(ts(v))
    except: return 0.0

def safe_div(a, b):
    return round(a / b, 4) if b else 0.0

def pct_str(v):
    return f"{round(v * 100, 1)}%"

def build_employee_row(r):
    """构建员工穿透明细行（通用）"""
    return {
        '工号': ts(r.get('工号', '')),
        '姓名': ts(r.get('姓名', '')),
        '三级部门': ts(r.get('三级部门', '')),
        '四级部门': ts(r.get('四级部门', '')),
        '五级部门': ts(r.get('五级部门', '')),
        '班次名称': ts(r.get('班次名称', '')),
        '班次上班时间': ts(r.get('班次上班时间', '')),
        '班次下班时间': ts(r.get('班次下班时间', '')),
        '首打卡时间': ts(r.get('首打卡时间', '')),
        '末打卡时间': ts(r.get('末打卡时间', '')),
    }

def build_over8h_employee(r):
    row = build_employee_row(r)
    row['超8H小时'] = tn(r.get('日超8H', 0))
    return row

def build_miss_employee(r):
    row = build_employee_row(r)
    row['缺卡次数'] = tn(r.get('缺卡次数', 0))
    row['班次内打卡次数'] = tn(r.get('班次内打卡次数', 0))
    row['标准打卡数'] = tn(r.get('标准打卡数', 0))
    return row

def build_correct_employee(r):
    row = build_employee_row(r)
    row['是否排班正确'] = ts(r.get('是否排班正确', ''))
    return row

def build_schedule_employee(r):
    row = build_employee_row(r)
    row['是否排班'] = ts(r.get('是否排班', ''))
    return row

# ============================================================
# 汇总一个分组
# ============================================================
def summarize(group_df):
    """对一组数据计算汇总指标 + 穿透工号"""
    # 去重（按工号）
    unique = group_df.drop_duplicates(subset=['工号'])
    total = len(unique)
    if total == 0:
        return {
            'total': 0,
            '日超8H': {'count': 0, 'rate': '0%', 'employees': []},
            '排班': {'已排班': 0, '未排班': 0, '排班率': '0%', 'employees_未排班': []},
            '排班正确': {'正确': 0, '不正确': 0, '不参与': 0, '正确率': '0%', 'employees_不正确': []},
            '缺卡': {'缺卡数量': 0, '缺卡率': '0%', '班次内打卡次数': 0, '标准打卡数': 0, 'employees': []},
            'HUB': {'total': 0, '正确': 0, '不正确': 0, '正确率': '0%', 'employees_不正确': []},
        }

    # 日超8H
    over8h_mask = group_df['是否日超8H'] == '是'
    over8h_count = int((unique['是否日超8H'] == '是').sum())
    over8h_employees = unique[unique['是否日超8H'] == '是']
    over8h_list = []
    for _, r in over8h_employees.iterrows():
        over8h_list.append(build_over8h_employee(r))

    # 排班
    scheduled = int((unique['是否排班'] == '是').sum())
    unscheduled = total - scheduled
    schedule_rate = safe_div(scheduled, total)
    unscheduled_employees = unique[unique['是否排班'] == '否']
    unscheduled_list = []
    for _, r in unscheduled_employees.iterrows():
        unscheduled_list.append(build_schedule_employee(r))

    # 排班正确
    correct = int((unique['是否排班正确'] == '正确').sum())
    incorrect = int((unique['是否排班正确'] == '不正确').sum())
    not_participate = int((unique['是否排班正确'] == '/').sum())
    correct_total = correct + incorrect
    correct_rate = safe_div(correct, correct_total)
    incorrect_employees = unique[unique['是否排班正确'] == '不正确']
    incorrect_list = []
    for _, r in incorrect_employees.iterrows():
        incorrect_list.append(build_correct_employee(r))

    # 缺卡 - 注意: dtype=str 时 .sum() 会做字符串拼接导致 inf, 必须先逐值转float再求和
    miss_sum = unique['缺卡次数'].apply(tn).sum()
    miss_employees = unique[unique['缺卡次数'].apply(tn) > 0]
    miss_list = []
    for _, r in miss_employees.iterrows():
        miss_list.append(build_miss_employee(r))

    # 班次内打卡次数 和 标准打卡数 汇总
    in_shift_total = round(unique['班次内打卡次数'].apply(tn).sum(), 1)
    standard_total = round(unique['标准打卡数'].apply(tn).sum(), 1)

    # HUB
    hub_mask = unique['HUB'] == 'hub'
    hub_total = int(hub_mask.sum())
    hub_correct = int((unique[hub_mask]['是否排班正确'] == '正确').sum())
    hub_incorrect = int((unique[hub_mask]['是否排班正确'] == '不正确').sum())
    hub_rate = safe_div(hub_correct, hub_correct + hub_incorrect)
    hub_incorrect_emp = unique[hub_mask & (unique['是否排班正确'] == '不正确')]
    hub_incorrect_list = []
    for _, r in hub_incorrect_emp.iterrows():
        hub_incorrect_list.append(build_correct_employee(r))

    return {
        'total': total,
        '日超8H': {
            'count': over8h_count,
            'rate': pct_str(safe_div(over8h_count, total)),
            'employees': over8h_list,
        },
        '排班': {
            '已排班': scheduled,
            '未排班': unscheduled,
            '排班率': pct_str(schedule_rate),
            'employees_未排班': unscheduled_list,
        },
        '排班正确': {
            '正确': correct,
            '不正确': incorrect,
            '不参与': not_participate,
            '正确率': pct_str(correct_rate),
            'employees_不正确': incorrect_list,
        },
        '缺卡': {
            '缺卡数量': round(miss_sum, 1),
            '缺卡率': pct_str(safe_div(miss_sum, len(unique) * 4)),  # 每人约4次打卡机会
            '班次内打卡次数': in_shift_total,
            '标准打卡数': standard_total,
            'employees': miss_list,
        },
        'HUB': {
            'total': hub_total,
            '正确': hub_correct,
            '不正确': hub_incorrect,
            '正确率': pct_str(hub_rate),
            'employees_不正确': hub_incorrect_list,
        },
    }

# ============================================================
# 主流程
# ============================================================
print("=" * 60)
print("读取指标计算后数据...")
df = pd.read_excel(INPUT_FILE, dtype=str)
print(f"数据行数: {len(df)}, 列数: {len(df.columns)}")

# 日期范围
dates = df['考勤日期'].dropna().unique()
date_str = f"{dates[0]} ~ {dates[-1]}" if len(dates) > 1 else str(dates[0])

print(f"考勤日期范围: {date_str}")

# --- 全公司 overview ---
print("\n计算全公司汇总...")
overview = summarize(df)
print(f"  总人数: {overview['total']}")

# --- 按部门分组 ---
print("\n按三级部门分组...")
departments = []
for dept3, grp3 in df.groupby('三级部门'):
    d3_name = ts(dept3)
    if d3_name == '':
        continue

    print(f"  处理: {d3_name}")

    # 三级汇总
    d3_summary = summarize(grp3)

    # 四级别明细
    sub_depts = []
    grp3_nonempty = grp3[grp3['四级部门'].apply(lambda x: ts(x) != '')]
    grp3_empty = grp3[grp3['四级部门'].apply(lambda x: ts(x) == '')]

    for d4, grp4 in grp3_nonempty.groupby('四级部门'):
        d4_name = ts(d4)
        sub_depts.append({
            'name': d4_name,
            'summary': summarize(grp4),
        })

    # 四级为空行
    if len(grp3_empty) > 0:
        sub_depts.append({
            'name': '/',
            'summary': summarize(grp3_empty),
        })

    # 按人数降序排列
    sub_depts.sort(key=lambda x: x['summary']['total'], reverse=True)

    departments.append({
        'name': d3_name,
        'summary': d3_summary,
        'sub_depts': sub_depts,
    })

# 按人数降序排列部门
departments.sort(key=lambda x: x['summary']['total'], reverse=True)

# --- 构建完整 JSON ---
report_data = {
    'meta': {
        'total_employees': overview['total'],
        'date_range': date_str,
        'department_count': len(departments),
    },
    'overview': overview,
    'departments': departments,
}

# --- 输出 ---
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(report_data, f, ensure_ascii=False, indent=2)

file_size = os.path.getsize(OUTPUT_FILE)
print(f"\n输出: {OUTPUT_FILE}")
print(f"文件大小: {file_size / 1024:.1f} KB")
print(f"部门数: {len(departments)}")
print("完成!")
