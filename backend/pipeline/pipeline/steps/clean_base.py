"""
多维表数据清理：保留最近7天记录，删除过期数据
"""
import sys, os, json, subprocess, time
from datetime import datetime, timedelta

BASE_TOKEN = "QgiQb585PaFST7secqHcqPKWnwc"
TABLE_ID   = "tblNIl6UjNO41lyK"
DATE_FIELD = "考勤日期"
KEEP_DAYS  = 7


def _lark(*args):
    """调用 lark-cli，返回 JSON 解析结果"""
    cmd = [r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.12.0\lark-cli.cmd"] + list(args) + ["--as", "user", "--format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"  lark-cli error: {r.stderr[:200]}")
        return {"ok": False}


def run(config=None):
    """
    清理飞书多维表中超过 KEEP_DAYS 天的历史数据。
    仅在 LARK_BASE_CLEANUP 环境变量为 '1' 时执行。
    """
    if os.environ.get("LARK_BASE_CLEANUP") != "1":
        print("多维表清理: 跳过 (LARK_BASE_CLEANUP != 1)")
        return

    print(f"=== 多维表数据清理 (保留最近{KEEP_DAYS}天) ===")

    # 1. 获取所有记录的日期
    all_dates = {}  # {record_id: date_str}
    offset = 0
    while True:
        resp = _lark("base", "+record-list",
                     "--base-token", BASE_TOKEN,
                     "--table-id", TABLE_ID,
                     "--field-id", DATE_FIELD,
                     "--limit", "200",
                     "--offset", str(offset))
        if not resp.get("ok"):
            print(f"  读取记录失败: {resp}")
            return

        records = resp["data"]["data"]
        for rec_id, row in zip(resp["data"]["record_id_list"], records):
            d = row[0][:10] if row and row[0] else ""
            if d:
                all_dates[rec_id] = d

        if not resp["data"].get("has_more"):
            break
        offset += 200

    if not all_dates:
        print("  无数据，跳过清理")
        return

    # 2. 计算保留窗口
    latest = max(all_dates.values())
    cutoff = (datetime.strptime(latest, "%Y-%m-%d") - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    print(f"  最新日期: {latest}, 保留窗口: {cutoff} ~ {latest}")

    # 3. 找出过期记录
    expired_ids = [rid for rid, d in all_dates.items() if d < cutoff]
    if not expired_ids:
        print(f"  无需清理 ({len(all_dates)} 条均在窗口内)")
        return

    print(f"  待清理: {len(expired_ids)} 条 ({len(all_dates)} 条中)")

    # 4. 批量删除（每次最多200条）
    BATCH = 200
    deleted = 0
    for i in range(0, len(expired_ids), BATCH):
        batch = expired_ids[i:i+BATCH]
        ids_json = json.dumps(batch, ensure_ascii=False)
        resp = _lark("base", "+record-delete",
                     "--base-token", BASE_TOKEN,
                     "--table-id", TABLE_ID,
                     "--record-ids", ids_json)
        if resp.get("ok"):
            deleted += len(batch)
            print(f"  已删除 {deleted}/{len(expired_ids)}")
        else:
            print(f"  删除失败: {resp.get('error', resp)}")
        if i + BATCH < len(expired_ids):
            time.sleep(2)

    print(f"  清理完成: 删除 {deleted} 条, 保留 {len(all_dates) - deleted} 条")


if __name__ == "__main__":
    run()
