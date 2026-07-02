"""
步骤2.5: 上传指标数据到趋势多维表
输入: 指标计算后数据.xlsx
目标: 飞书多维表「每日考勤明细」(QgiQb585PaFST7secqHcqPKWnwc / tblNIl6UjNO41lyK)
用于支撑7日趋势图
"""
import os, sys, json, subprocess, time
sys.path.insert(0, r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages")
import pandas as pd

LARK_CLI = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.12.0\lark-cli.cmd"

BASE_TOKEN = "QgiQb585PaFST7secqHcqPKWnwc"
TABLE_ID = "tblNIl6UjNO41lyK"

# 指标列 → 趋势表字段名映射
FIELD_MAP = {
    '考勤日期': '考勤日期', '工号': '工号', '姓名': '姓名',
    '三级部门': '三级部门', '四级部门': '四级部门', '五级部门': '五级部门',
    '班次名称': '班次名称', '班次上班时间': '班次上班时间', '班次下班时间': '班次下班时间',
    '首打卡时间': '首打卡时间', '末打卡时间': '末打卡时间',
    '班次内打卡次数': '班次内打卡次数', '标准打卡数': '标准打卡数',
    '是否排班正确': '是否排班正确', '是否排班': '是否排班',
    '是否日超8H': '是否日超8H', '日超8H': '日超8H', '缺卡数': '缺卡数',
    '每日总工时': '每日总工时', '本周累计加班工时': '本周累计加班工时',
    '上周累计加班工时': '上周累计加班工时', '补签数': '补签数',
    'HUB': 'HUB', '备注（GF）': '备注',
}


def to_str(v):
    if pd.isna(v) or v is None:
        return ''
    return str(v).strip()


def run(config):
    metrics_file = config['metrics_file']
    workspace = config['workspace']

    df = pd.read_excel(metrics_file, dtype=str)
    print(f"指标数据: {len(df)} 行")

    available_cols = [c for c in FIELD_MAP if c in df.columns]
    fields = [FIELD_MAP[c] for c in available_cols]

    # 构建所有行
    rows = []
    for _, r in df.iterrows():
        row = []
        for col in available_cols:
            val = to_str(r.get(col, ''))
            row.append(val if val else None)
        rows.append(row)

    # 分批上传 (200/批)
    batch_size = 200
    total = (len(rows) + batch_size - 1) // batch_size

    for i in range(total):
        start = i * batch_size
        end = min(start + batch_size, len(rows))
        batch = rows[start:end]
        payload = {"fields": fields, "rows": batch}

        batch_file = os.path.join(workspace, f'_trend_batch_{i}.json')
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)

        # 调用 lark-cli 上传
        cmd = [
            LARK_CLI, 'base', '+record-batch-create',
            '--base-token', BASE_TOKEN,
            '--table-id', TABLE_ID,
            '--as', 'user',
            '--json', f'@_trend_batch_{i}.json'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=workspace)
        ok = '"ok": true' in result.stdout or '"ok":true' in result.stdout

        # 清理临时文件
        try:
            os.remove(batch_file)
        except OSError:
            pass

        if ok:
            print(f"  批次 {i+1}/{total}: {len(batch)} 行 ✓")
            if i < total - 1:
                time.sleep(0.5)
        else:
            err = result.stdout[:200] if result.stdout else result.stderr[:200]
            print(f"  批次 {i+1}/{total}: 失败 - {err}")
            return

    print(f"趋势表更新完成: {len(rows)} 行")
