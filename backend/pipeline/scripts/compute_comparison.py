"""
同比变化计算脚本。
比较昨天(前次)透视分析.xlsx 与 今天 report_data.json，输出 comparison_data.json。

用法:
    python compute_comparison.py <今天工作目录> <昨天工作目录>

示例:
    python compute_comparison.py C:/Users/.../2026-05-22-xxx C:/Users/.../2026-05-21-xxx
"""
import sys
import pandas as pd
import json
import os

# ===== 配置 =====
if len(sys.argv) >= 3:
    WORKSPACE = sys.argv[1]
    PREV_WORKSPACE = sys.argv[2]
else:
    print("用法: python compute_comparison.py <今天工作目录> <昨天工作目录>")
    sys.exit(1)

regions_map = {
    'FL': 'FL 佛州大区',
    'TX': 'TX 德州大区',
    'GL': 'GL 大湖大区',
    'WE': 'WE 美西大区',
    'MS': 'MS 中南大区',
    'NE': 'NE 东北大区',
    'Ground项目部': 'Ground项目部'
}

# ===== 读取昨天透视分析 =====
xlsx_path = os.path.join(PREV_WORKSPACE, '透视分析.xlsx')
if not os.path.exists(xlsx_path):
    print(f"错误: 找不到昨天的透视分析文件: {xlsx_path}")
    sys.exit(1)

yesterday = {}
for sheet_name in ['日超8H', '是否排班', '是否排班正确', '缺卡', 'hub排班是否正确']:
    try:
        df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
    except Exception as e:
        print(f"警告: 无法读取Sheet '{sheet_name}': {e}")
        continue

    # 公司整体
    summaries = df[df['四级部门'] == '汇总']
    if sheet_name == '日超8H':
        yesterday['__overview__超标率'] = float(summaries['超过人数'].sum() / summaries['总计人数'].sum())
    elif sheet_name == '是否排班':
        total_scheduled = int(summaries['已排班数'].sum())
        total_emp = int(summaries['总计人数'].sum())
        yesterday['__overview__排班率'] = total_scheduled / total_emp if total_emp > 0 else 0
    elif sheet_name == '是否排班正确':
        tot_correct = int(summaries['正确数量'].sum())
        tot_incorrect = int(summaries['不正确数量'].sum())
        tot = tot_correct + tot_incorrect
        yesterday['__overview__正确率'] = tot_correct / tot if tot > 0 else 0
    elif sheet_name == '缺卡':
        tot_miss = int(summaries['缺卡数量'].sum())
        tot_std = int(summaries['标准打卡数量'].sum())
        yesterday['__overview__缺卡率'] = tot_miss / tot_std if tot_std > 0 else 0
    elif sheet_name == 'hub排班是否正确':
        yesterday['__overview__hub正确率'] = float(df['正确'].sum() / (df['正确'].sum() + df['不正确'].sum()))

    # 各大区
    for rk, rn in regions_map.items():
        if rk not in yesterday:
            yesterday[rk] = {}
        row = df[df['三级部门'] == rn]
        if len(row) == 0:
            continue
        if sheet_name == 'hub排班是否正确':
            summary = row[row['四级部门'].isna() | (row['四级部门'] == '汇总')]
            if len(summary) == 0:
                summary = row.iloc[-1:]
            s = summary.iloc[0]
            yesterday[rk]['hub正确率'] = float(s['正确率']) if pd.notna(s['正确率']) else 0
            continue

        summary = row[row['四级部门'] == '汇总']
        if len(summary) == 0:
            continue
        s = summary.iloc[0]
        if sheet_name == '日超8H':
            yesterday[rk]['超标率'] = float(s['超过人数'] / s['总计人数']) if s['总计人数'] > 0 else 0
        elif sheet_name == '是否排班':
            yesterday[rk]['排班率'] = float(s['排班率'])
        elif sheet_name == '是否排班正确':
            yesterday[rk]['正确率'] = float(s['正确率'])
        elif sheet_name == '缺卡':
            yesterday[rk]['缺卡率'] = float(s['缺卡率'])

print("=== 昨天数据 ===")
for k, v in yesterday.items():
    print(f'{k}: {v}')

# ===== 读取今天 report_data.json =====
json_path = os.path.join(WORKSPACE, 'report_data.json')
if not os.path.exists(json_path):
    print(f"错误: 找不到 report_data.json: {json_path}")
    sys.exit(1)

with open(json_path, 'r', encoding='utf-8') as f:
    report = json.load(f)

overview = report.get('overview', {})
today = {}

o8 = overview.get('日超8H', {})
pb = overview.get('排班', {})
pbc = overview.get('排班正确', {})
qk = overview.get('缺卡', {})
hub = overview.get('HUB', {})

today['__overview__超标率'] = float(o8.get('rate', '0%').rstrip('%')) / 100
today['__overview__排班率'] = float(pb.get('排班率', '0%').rstrip('%')) / 100
today['__overview__正确率'] = float(pbc.get('正确率', '0%').rstrip('%')) / 100
today['__overview__缺卡率'] = float(qk.get('缺卡率', '0%').rstrip('%')) / 100
today['__overview__hub正确率'] = float(hub.get('正确率', '0%').rstrip('%')) / 100

deps = report.get('departments', [])
for dep in deps:
    name = dep.get('name', '')
    if name not in regions_map.values():
        continue
    rk = None
    for k, v in regions_map.items():
        if v == name:
            rk = k
            break
    if rk is None:
        continue
    sub_depts = dep.get('sub_depts', [])
    total_emp = 0
    exceed = 0
    scheduled = 0
    unscheduled = 0
    correct = 0
    incorrect = 0
    miss = 0
    standard = 0

    for sd in sub_depts:
        s = sd.get('summary', {})
        total_emp += s.get('total', 0)
        exceed += s.get('日超8H', {}).get('count', 0)
        scheduled += s.get('排班', {}).get('已排班', 0)
        unscheduled += s.get('排班', {}).get('未排班', 0)
        correct += s.get('排班正确', {}).get('正确', 0)
        incorrect += s.get('排班正确', {}).get('不正确', 0)
        miss += int(s.get('缺卡', {}).get('缺卡数量', 0))
        standard += int(s.get('缺卡', {}).get('标准打卡数', 0))

    today[rk] = {
        '超标率': exceed / total_emp if total_emp > 0 else 0,
        '排班率': scheduled / (scheduled + unscheduled) if (scheduled + unscheduled) > 0 else 0,
        '正确率': correct / (correct + incorrect) if (correct + incorrect) > 0 else 0,
        '缺卡率': miss / standard if standard > 0 else 0,
    }

print()
print("=== 今天数据 ===")
for k, v in today.items():
    print(f'{k}: {v}')


# ===== 对比计算 =====
def compare(name, y, t, good_dir):
    if abs(y) < 0.0001 and abs(t) < 0.0001:
        return {'name': name, 'yesterday': y, 'today': t, 'diff_pct': 0, 'diff_pp': 0, 'arrow': '→', 'color': 'gray', 'text': '持平'}
    if abs(y) < 0.0001:
        return {'name': name, 'yesterday': y, 'today': t, 'diff_pct': None, 'diff_pp': t*100, 'arrow': '↑', 'color': 'green' if good_dir == 'up' else 'red', 'text': f'+{t*100:.1f}%'}

    diff = t - y
    diff_pct = diff / y * 100
    diff_pp = diff * 100

    if abs(diff) < 0.0001:
        arrow, color = '→', 'gray'
    elif diff > 0:
        arrow = '↑'
        color = 'green' if good_dir == 'up' else 'red'
    else:
        arrow = '↓'
        color = 'red' if good_dir == 'up' else 'green'

    sgn = '+' if diff > 0 else ''
    return {'name': name, 'yesterday': y, 'today': t, 'diff_pct': diff_pct, 'diff_pp': diff_pp, 'arrow': arrow, 'color': color, 'text': f'{sgn}{diff_pp:.1f}%'}


results = {}

# 公司整体
overview_metrics = [('超标率', 'down'), ('排班率', 'up'), ('正确率', 'up'), ('缺卡率', 'down'), ('HUB正确率', 'up')]
overview_keys = ['__overview__超标率', '__overview__排班率', '__overview__正确率', '__overview__缺卡率', '__overview__hub正确率']
results['__overview__'] = {}
for i, (name, dr) in enumerate(overview_metrics):
    k = overview_keys[i]
    if k in yesterday and k in today:
        results['__overview__'][name] = compare(name, yesterday[k], today[k], dr)

# 各大区
for rk in ['FL', 'TX', 'GL', 'WE', 'MS', 'NE', 'Ground项目部']:
    yd = yesterday.get(rk, {})
    td = today.get(rk, {})
    rr = {}
    for name, dr in [('超标率', 'down'), ('排班率', 'up'), ('正确率', 'up'), ('缺卡率', 'down')]:
        if name in yd and name in td:
            rr[name] = compare(name, yd[name], td[name], dr)
    if 'hub正确率' in yd:
        hub_t = today.get('__overview__hub正确率', yd['hub正确率'])
        rr['HUB正确率'] = compare('HUB正确率', yd['hub正确率'], hub_t, 'up')
    results[rk] = rr

print()
print("=== 对比结果 ===")
for rk, rr in results.items():
    print(f'{rk}:')
    for name, c in rr.items():
        print(f'  {name}: {c["yesterday"]*100:.1f}% → {c["today"]*100:.1f}% | {c["arrow"]} {c["text"]} [{c["color"]}]')

out_path = os.path.join(WORKSPACE, 'comparison_data.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print()
print(f"已保存: {out_path}")
