"""
构建7日趋势数据：从飞书多维表查询历史记录，按日期+部门聚合指标
"""
import sys, os, json, subprocess
sys.path.insert(0, r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages")
import pandas as pd
from datetime import datetime, timedelta

BASE_TOKEN = "QgiQb585PaFST7secqHcqPKWnwc"
TABLE_ID   = "tblNIl6UjNO41lyK"


LARK_CLI = r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.12.0\lark-cli.cmd"

def _lark(*args):
    cmd = [LARK_CLI] + list(args) + ["--as", "user", "--format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False}


def _fetch_all_records():
    """从多维表获取全部记录"""
    all_rows = []
    offset = 0
    while True:
        resp = _lark("base", "+record-list",
                     "--base-token", BASE_TOKEN,
                     "--table-id", TABLE_ID,
                     "--field-id", "考勤日期",
                     "--field-id", "三级部门",
                     "--field-id", "四级部门",
                     "--field-id", "五级部门",
                     "--field-id", "班次内打卡次数",
                     "--field-id", "标准打卡数",
                     "--field-id", "是否排班",
                     "--field-id", "是否排班正确",
                     "--field-id", "是否日超8H",
                     "--field-id", "每日总工时",
                     "--field-id", "日超8H",
                     "--field-id", "本周累计加班工时",
                     "--field-id", "上周累计加班工时",
                     "--limit", "200",
                     "--offset", str(offset))
        if not resp.get("ok"):
            break
        data = resp["data"]
        fids = data.get("field_id_list", [])
        for row in data.get("data", []):
            rec = {}
            for i, fid in enumerate(fids):
                val = row[i] if i < len(row) else ""
                if isinstance(val, list):
                    val = val[0] if val else ""
                rec[fid] = str(val).strip() if val else ""
            all_rows.append(rec)
        if not data.get("has_more"):
            break
        offset += 200
    return all_rows


def run(config=None):
    """构建 trend_data.json"""
    print("=== 步骤: 构建7日趋势数据 ===")
    
    rows = _fetch_all_records()
    if not rows:
        print("  多维表无数据，跳过趋势构建")
        return

    # Field ID → name mapping from the batch upload field list
    fid_map = {
        'fldjHOW6OG': '考勤日期', 'fldGuKEySZ': '三级部门', 'fld0T3ICNB': '四级部门',
        'fldJw3jq0M': '五级部门', 'fldDYuf22A': '是否排班', 'fldVRiO7KP': '是否排班正确',
        'fldVdZdf7x': '是否日超8H', 'fldWcl3gey': '班次内打卡次数',
        'fldcwml15o': '标准打卡数', 'fldrlJqMu8': '每日总工时',
        'fldOcRGN0u': '日超8H', 'fld4QwkvGN': '本周累计加班工时',
        'fldVnWSysG': '上周累计加班工时',
    }

    # Convert to DataFrame
    records = []
    for r in rows:
        rec = {}
        for fid, name in fid_map.items():
            val = r.get(fid, '')
            rec[name] = val
        records.append(rec)

    df = pd.DataFrame(records)
    if df.empty:
        print("  无有效记录")
        return

    # Parse date and filter to last 7 days
    df['_date'] = pd.to_datetime(df['考勤日期'].str[:10], errors='coerce')
    df = df.dropna(subset=['_date'])
    if df.empty:
        print("  无有效日期")
        return

    latest = df['_date'].max().strftime('%Y-%m-%d')
    cutoff = df['_date'].max() - timedelta(days=7)
    df_week = df[df['_date'] > cutoff].copy()
    dates_sorted = sorted(df_week['_date'].dt.strftime('%Y-%m-%d').unique())

    # Parse numeric fields
    for col in ['班次内打卡次数', '标准打卡数', '每日总工时', '日超8H', '本周累计加班工时', '上周累计加班工时']:
        if col in df_week.columns:
            df_week[col] = pd.to_numeric(df_week[col], errors='coerce').fillna(0)

    # Aggregate functions
    def _agg_dept(grp):
        total = len(grp)
        scheduled = (grp['是否排班'] == '是').sum()
        correct = (grp['是否排班正确'] == '正确').sum()
        punch_sum = grp['班次内打卡次数'].sum()
        std_sum = grp['标准打卡数'].sum()
        over8h = grp['日超8H'].sum()
        ot_this = grp['本周累计加班工时'].sum()
        ot_last = grp['上周累计加班工时'].sum()
        return pd.Series({
            '总人数': total, '已排班': scheduled, '排班率': round(scheduled/total*100) if total > 0 else 0,
            '正确数': correct, '正确率': round(correct/(scheduled if scheduled > 0 else 1)*100),
            '打卡数': round(punch_sum, 1), '标准打卡数': round(std_sum, 1),
            '打卡率': min(round(punch_sum/std_sum*100), 100) if std_sum > 0 else 0,
            '日超8H合计': round(over8h, 1), '本周加班': round(ot_this, 1), '上周加班': round(ot_last, 1),
        })

    # Build trend: 全公司 by date
    overview_trend = {}
    for d in dates_sorted:
        day_df = df_week[df_week['_date'] == d]
        overview_trend[d] = _agg_dept(day_df).to_dict()

    # Build trend: by 三级部门 + date
    dept_trend = {}
    for dept in sorted(df_week['三级部门'].unique()):
        dept_df = df_week[df_week['三级部门'] == dept]
        dept_trend[dept] = {}
        for d in dates_sorted:
            day_df = dept_df[dept_df['_date'] == d]
            if len(day_df) > 0:
                dept_trend[dept][d] = _agg_dept(day_df).to_dict()

    # Build trend: by 四级部门 + date  
    sub_trend = {}
    for _, r in df_week.iterrows():
        key = f"{r['三级部门']}|{r['四级部门']}"
        if key not in sub_trend:
            sub_trend[key] = {}
    for dept in sorted(df_week['三级部门'].unique()):
        dept_df = df_week[df_week['三级部门'] == dept]
        for sub in sorted(dept_df['四级部门'].dropna().unique()):
            key = f"{dept}|{sub}"
            sub_df = dept_df[dept_df['四级部门'] == sub]
            sub_trend[key] = {}
            for d in dates_sorted:
                day_df = sub_df[sub_df['_date'] == d]
                if len(day_df) > 0:
                    sub_trend[key][d] = _agg_dept(day_df).to_dict()

    trend_data = {
        'dates': dates_sorted,
        'latest_date': latest,
        'overview': overview_trend,
        'departments': dept_trend,
        'sub_departments': sub_trend,
    }

    output = config.get('trend_json', os.path.join(config.get('workspace', '.'), 'trend_data.json'))
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(trend_data, f, ensure_ascii=False, default=str)
    print(f"  趋势数据已生成: {output}")
    print(f"  日期范围: {dates_sorted[0]} ~ {dates_sorted[-1]} ({len(dates_sorted)}天)")
    print(f"  三级部门: {len(dept_trend)}, 四级部门: {len(sub_trend)}")


if __name__ == '__main__':
    run({'workspace': os.getcwd(), 'trend_json': os.path.join(os.getcwd(), 'trend_data.json')})
