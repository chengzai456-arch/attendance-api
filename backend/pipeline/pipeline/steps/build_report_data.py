"""
步骤4a: 构建 HTML 报告所需的完整 JSON 数据（含穿透明细）
输入: 指标计算后数据.xlsx
输出: report_data.json
"""
import os
import json
import pandas as pd
import numpy as np

from pipeline.utils import to_str as ts, to_num as tn, safe_div, pct_str


def _build_employee_row(r):
    """构建员工穿透明细行（精简版：仅核心字段，用于全员列表）"""
    return {
        '工号': ts(r.get('工号', '')),
        '姓名': ts(r.get('姓名', '')),
        '三级部门': ts(r.get('三级部门', '')),
        '四级部门': ts(r.get('四级部门', '')),
        '五级部门': ts(r.get('五级部门', '')),
    }


def _build_employee_detail(r):
    """构建员工穿透明细行（详细版：含班次/打卡/备注等，用于指标穿透）"""
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
        '备注（GF）': ts(r.get('备注（GF）', '')),
        '是否排班正确': ts(r.get('是否排班正确', '')),
        '是否排班': ts(r.get('是否排班', '')),
        '缺卡数': tn(r.get('缺卡数', 0)),
        '班次内打卡次数': tn(r.get('班次内打卡次数', 0)),
        '标准打卡数': tn(r.get('标准打卡数', 0)),
        '日超8H': tn(r.get('日超8H', 0)),
        '补签数': tn(r.get('补签数', 0)),
    }


def _build_over8h_employee(r):
    row = _build_employee_detail(r)
    row['超8H小时'] = tn(r.get('日超8H', 0))
    return row


def _build_miss_employee(r):
    row = _build_employee_detail(r)
    return row


def _build_correct_employee(r):
    row = _build_employee_detail(r)
    return row


def _build_schedule_employee(r):
    row = _build_employee_detail(r)
    return row


def _build_ot_employee(r):
    """OT加班穿透"""
    row = _build_employee_detail(r)
    row['本周加班工时'] = tn(r.get('本周累计加班工时', 0))
    row['上周加班工时'] = tn(r.get('上周累计加班工时', 0))
    return row


def summarize(group_df):
    """对一组数据计算汇总指标 + 穿透工号"""
    unique = group_df.drop_duplicates(subset=['工号'])
    total = len(unique)
    # 全员列表（供人数穿透）
    all_employees = [_build_employee_row(r) for _, r in unique.iterrows()]
    if total == 0:
        return {
            'total': 0,
            'all_employees': [],
            '本周加班工时': 0,
            '上周加班工时': 0,
            '日超8H': {'count': 0, 'total_hours': 0, 'rate': '0%', 'employees': []},
            '排班': {'已排班': 0, '未排班': 0, '排班率': '0%', 'employees_未排班': []},
            '排班正确': {'正确': 0, '不正确': 0, '不参与': 0, '正确率': '0%', 'employees_不正确': []},
            '打卡率': {'打卡率': '0%', '打卡数': 0, '标准打卡数': 0, '缺卡数': 0, '补签数_emp': 0, '缺卡数_emp': 0, '补签率': '0%', '班次内打卡次数': 0, 'employees': []},
            'HUB': {'total': 0, '正确': 0, '不正确': 0, '正确率': '0%', 'employees_不正确': []},
        }

    # 日超8H
    over8h_employees = unique[unique['是否日超8H'] == '是']
    over8h_count = len(over8h_employees)
    over8h_total_hours = round(unique['日超8H'].apply(tn).sum(), 2)  # 超8H工时合计
    over8h_list = [_build_over8h_employee(r) for _, r in over8h_employees.iterrows()]

    # 排班
    scheduled = int((unique['是否排班'] == '是').sum())
    unscheduled = total - scheduled
    schedule_rate = safe_div(scheduled, total)
    unscheduled_employees = unique[unique['是否排班'] == '否']
    unscheduled_list = [_build_schedule_employee(r) for _, r in unscheduled_employees.iterrows()]

    # 排班正确
    correct = int((unique['是否排班正确'] == '正确').sum())
    incorrect = int((unique['是否排班正确'] == '不正确').sum())
    not_participate = int((unique['是否排班正确'] == '/').sum())
    correct_total = correct + incorrect
    correct_rate = safe_div(correct, correct_total)
    incorrect_employees = unique[unique['是否排班正确'] == '不正确']
    incorrect_list = [_build_correct_employee(r) for _, r in incorrect_employees.iterrows()]

    # 缺卡 / 打卡率
    miss_sum = unique['缺卡数'].apply(tn).sum()
    punch_sum = unique['班次内打卡次数'].apply(tn).sum()
    standard_total = round(unique['标准打卡数'].apply(tn).sum(), 1)
    # 打卡率 = min(打卡数 / 标准打卡数, 100%)
    punch_rate = min(safe_div(punch_sum, standard_total), 1.0)
    # 缺卡数
    miss_num = miss_sum
    # 补签率: 按唯一工号聚合
    emp_agg = unique.groupby('工号').agg({
        '补签数': 'first',
        '缺卡数': lambda x: x.apply(tn).sum()
    })
    bq_emp_sum = emp_agg['补签数'].apply(tn).sum()
    qk_emp_sum = emp_agg['缺卡数'].sum()
    buqian_rate = safe_div(bq_emp_sum, bq_emp_sum + qk_emp_sum)
    
    miss_employees = unique[unique['缺卡数'].apply(tn) > 0]
    miss_list = [_build_miss_employee(r) for _, r in miss_employees.iterrows()]

    # 加班工时
    overtime_this_week = round(unique['本周累计加班工时'].apply(tn).sum(), 1)
    overtime_last_week = round(unique['上周累计加班工时'].apply(tn).sum(), 1)
    # OT穿透 - 本周
    ot_this_week_emp = unique[unique['本周累计加班工时'].apply(tn) > 0]
    ot_this_week_list = [_build_ot_employee(r) for _, r in ot_this_week_emp.iterrows()]
    # OT穿透 - 上周
    ot_last_week_emp = unique[unique['上周累计加班工时'].apply(tn) > 0]
    ot_last_week_list = [_build_ot_employee(r) for _, r in ot_last_week_emp.iterrows()]

    # HUB
    hub_mask = unique['HUB'] == 'hub'
    hub_total = int(hub_mask.sum())
    hub_correct = int((unique[hub_mask]['是否排班正确'] == '正确').sum())
    hub_incorrect = int((unique[hub_mask]['是否排班正确'] == '不正确').sum())
    hub_rate = safe_div(hub_correct, hub_total)
    hub_incorrect_emp = unique[hub_mask & (unique['是否排班正确'] == '不正确')]
    hub_incorrect_list = [_build_correct_employee(r) for _, r in hub_incorrect_emp.iterrows()]

    return {
        'total': total,
        'all_employees': all_employees,
        '本周加班工时': overtime_this_week,
        '上周加班工时': overtime_last_week,
        'employees_本周OT': ot_this_week_list,
        'employees_上周OT': ot_last_week_list,
        '日超8H': {
            'count': over8h_count,
            'total_hours': over8h_total_hours,
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
        '打卡率': {
            '打卡率': pct_str(punch_rate),
            '打卡数': round(punch_sum, 1),
            '标准打卡数': standard_total,
            '缺卡数': round(miss_num, 1),
            '补签数_emp': round(bq_emp_sum, 1),
            '缺卡数_emp': round(qk_emp_sum, 1),
            '补签率': pct_str(buqian_rate, 1),
            '班次内打卡次数': round(punch_sum, 1),
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


def run(config):
    """构建报告 JSON 数据"""
    input_file  = config['metrics_file']
    output_file = config['report_json']

    print("=" * 60)
    print("读取指标计算后数据...")
    df = pd.read_excel(input_file, dtype=str)
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

        d3_summary = summarize(grp3)

        # 四级别明细
        sub_depts = []
        grp3_nonempty = grp3[grp3['四级部门'].apply(lambda x: ts(x) != '')]
        grp3_empty = grp3[grp3['四级部门'].apply(lambda x: ts(x) == '')]

        for d4, grp4 in grp3_nonempty.groupby('四级部门'):
            d4_name = ts(d4)
            # 五级部门聚合
            l5_depts = []
            grp4_nonempty = grp4[grp4['五级部门'].apply(lambda x: ts(x) != '')]
            if len(grp4_nonempty) > 0:
                for d5, grp5 in grp4_nonempty.groupby('五级部门'):
                    d5_name = ts(d5)
                    l5_depts.append({
                        'name': d5_name,
                        'summary': summarize(grp5),
                    })
                l5_depts.sort(key=lambda x: x['summary']['total'], reverse=True)
            sub_depts.append({
                'name': d4_name,
                'summary': summarize(grp4),
                'l5_depts': l5_depts,
            })

        if len(grp3_empty) > 0:
            sub_depts.append({
                'name': '/',
                'summary': summarize(grp3_empty),
            })

        sub_depts.sort(key=lambda x: x['summary']['total'], reverse=True)

        departments.append({
            'name': d3_name,
            'summary': d3_summary,
            'sub_depts': sub_depts,
        })

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
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(output_file)
    print(f"\n输出: {output_file}")
    print(f"文件大小: {file_size / 1024:.1f} KB")
    print(f"部门数: {len(departments)}")
    print("完成!")
